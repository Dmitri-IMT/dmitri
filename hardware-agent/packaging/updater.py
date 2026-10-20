#!/usr/bin/python3
# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

STATE_DIR = Path("/var/lib/dmitri/updates")
RUNTIME_DIR = Path("/run/dmitri-agent-updater")
GATE_PATH = Path("/var/lib/dmitri/update-gate.json")
SCAN_CHECKPOINT_PATH = Path("/var/lib/dmitri/scan-finalization.json")
SCAN_LOCK_PATH_FILE = Path("/usr/lib/dmitri/scan-lock-path")
SCAN_LOCK_PATH = Path("/var/lib/dmitri/scan.lock")
AGENT_ROOT = Path("/opt/dmitri-agent")
AGENT_ENV = Path("/etc/dmitri/agent.env")
PACKAGE_CACHE = STATE_DIR / "cache"
APT_SOURCE_LIST = Path("/etc/apt/sources.list")
APT_SOURCE_DIR = Path("/etc/apt/sources.list.d")
APT_KEYRING_DIR = Path("/etc/apt/keyrings")
APT_LIST_DIR = Path("/var/lib/apt/lists")
SOCKET_PATH = RUNTIME_DIR / "control.sock"
MAX_MESSAGE_BYTES = 4096
CHECK_TIMEOUT_SECONDS = 600
CLIENT_TIMEOUT_SECONDS = CHECK_TIMEOUT_SECONDS + 30
# Runtime compatibility level. This is independent of Debian package version.
UPDATER_COMPAT_LEVEL = 1
ACTIVE_PHASES = (
    "requested",
    "preparing",
    "installing",
    "verifying",
    "recovering",
    "needs_intervention",
)
PHASES = (
    "requested",
    "preparing",
    "installing",
    "verifying",
    "recovering",
    "rolled_back",
    "needs_intervention",
    "failed",
    "expired",
    "succeeded",
)


class StateCorrupt(Exception):
    pass


class Updater:
    def __init__(
        self,
        state_dir: Path = STATE_DIR,
        runtime_dir: Path = RUNTIME_DIR,
        gate_path: Path = GATE_PATH,
        scan_checkpoint_path: Path = SCAN_CHECKPOINT_PATH,
        readiness_identity: Any = None,
        package_version: Any = None,
        app_version: Any = None,
    ) -> None:
        self.state_dir = state_dir
        self.runtime_dir = runtime_dir
        self.journal_path = state_dir / "state.sqlite3"
        self.gate_path = gate_path
        self.scan_checkpoint_path = scan_checkpoint_path
        self.readiness_identity = readiness_identity or self._systemd_agent_identity
        self.package_version = package_version or self._installed_agent_package_version
        self.app_version = app_version or self._installed_agent_app_version
        self.socket_path = runtime_dir / "control.sock"
        self.mutex_path = runtime_dir / "transaction.lock"
        self.stopping = threading.Event()
        self.server_socket: socket.socket | None = None
        self.last_readiness: tuple[int, str, str, str] | None = None
        self.child_lock = threading.Lock()
        self.children: set[subprocess.Popen[bytes]] = set()
        self.http_forbidden = threading.Event()
        self.report_retry_delay = 5

    def initialize(self) -> None:
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)
        os.chmod(self.runtime_dir, 0o700)
        if not self.journal_path.exists():
            with closing(self._connect()) as connection:
                with connection:
                    phase_values = ",".join(repr(phase) for phase in PHASES)
                    connection.execute(
                        "CREATE TABLE operations (operation_id TEXT PRIMARY KEY, "
                        f"phase TEXT NOT NULL CHECK (phase IN ({phase_values})))"
                    )
                    connection.execute(
                        "CREATE TABLE update_details (operation_id TEXT PRIMARY KEY, "
                        "session_id TEXT NOT NULL, release_id TEXT NOT NULL, target_version TEXT NOT NULL, "
                        "sha256 TEXT NOT NULL, deadline TEXT NOT NULL, prior_version TEXT, "
                        "snapshot TEXT, phase TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0, "
                        "pending_event TEXT, invocation_id TEXT, error_code TEXT, ack_sequence INTEGER NOT NULL DEFAULT 0, "
                        "recovery_attempts INTEGER NOT NULL DEFAULT 0)"
                    )
                    connection.execute(
                        "CREATE TABLE update_events (operation_id TEXT NOT NULL, sequence INTEGER NOT NULL, "
                        "body TEXT NOT NULL, PRIMARY KEY(operation_id, sequence))"
                    )
                    connection.execute("PRAGMA user_version = 1")
        else:
            # Add companion transaction tables without rewriting the Task 3 journal.
            try:
                with closing(self._connect()) as connection, connection:
                    if connection.execute("PRAGMA integrity_check").fetchone() != (
                        "ok",
                    ):
                        raise StateCorrupt("journal integrity")
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS update_details (operation_id TEXT PRIMARY KEY, "
                        "session_id TEXT NOT NULL, release_id TEXT NOT NULL, target_version TEXT NOT NULL, "
                        "sha256 TEXT NOT NULL, deadline TEXT NOT NULL, prior_version TEXT, "
                        "snapshot TEXT, phase TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0, "
                        "pending_event TEXT, invocation_id TEXT, error_code TEXT, ack_sequence INTEGER NOT NULL DEFAULT 0, "
                        "recovery_attempts INTEGER NOT NULL DEFAULT 0)"
                    )
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS update_events (operation_id TEXT NOT NULL, sequence INTEGER NOT NULL, "
                        "body TEXT NOT NULL, PRIMARY KEY(operation_id, sequence))"
                    )
                    columns = {
                        row[1]
                        for row in connection.execute(
                            "PRAGMA table_info(update_details)"
                        ).fetchall()
                    }
                    if "recovery_attempts" not in columns:
                        connection.execute(
                            "ALTER TABLE update_details ADD COLUMN recovery_attempts INTEGER NOT NULL DEFAULT 0"
                        )
            except (sqlite3.DatabaseError, StateCorrupt):
                # Preserve a damaged journal; _restore_gate records the fail-closed gate.
                pass
        os.chmod(self.journal_path, 0o600)
        self._restore_gate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.journal_path, timeout=5)
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _active_operations(self) -> list[str]:
        try:
            with closing(self._connect()) as connection, connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if integrity != ("ok",):
                    raise StateCorrupt("integrity")
                columns = connection.execute("PRAGMA table_info(operations)").fetchall()
                if not {"operation_id", "phase"}.issubset({row[1] for row in columns}):
                    raise StateCorrupt("schema")
                rows = connection.execute(
                    "SELECT operation_id, phase FROM operations ORDER BY operation_id"
                ).fetchall()
                if any(phase not in PHASES for _, phase in rows):
                    raise StateCorrupt("phase")
                return [
                    operation_id
                    for operation_id, phase in rows
                    if phase in ACTIVE_PHASES
                ]
        except (sqlite3.DatabaseError, OSError) as exc:
            raise StateCorrupt("journal") from exc

    def _write_gate(self, reason: str, operation_ids: list[str]) -> None:
        self.gate_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        payload = json.dumps(
            {"blocked": True, "reason": reason, "operation_ids": operation_ids},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        temporary = self.gate_path.with_name(
            f".{self.gate_path.name}.{uuid.uuid4().hex}.tmp"
        )
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o644)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.gate_path)
            if os.name == "posix":
                directory = os.open(self.gate_path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    def _clear_gate(self) -> None:
        try:
            self.gate_path.unlink()
        except FileNotFoundError:
            return
        if os.name == "posix":
            directory = os.open(self.gate_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def _remove_from_operation_gate(self, update_id: str) -> None:
        if not self.gate_path.exists():
            return
        try:
            gate = json.loads(self.gate_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        operation_ids = gate.get("operation_ids") if isinstance(gate, dict) else None
        if (
            not isinstance(gate, dict)
            or gate.get("blocked") is not True
            or gate.get("reason") != "operation_pending"
            or not isinstance(operation_ids, list)
            or update_id not in operation_ids
        ):
            return
        remaining = [item for item in operation_ids if item != update_id]
        if remaining:
            self._write_gate("operation_pending", remaining)
        else:
            self._clear_gate()

    def _restore_gate(self) -> None:
        gate_corrupt = False
        if self.gate_path.exists():
            try:
                gate = json.loads(self.gate_path.read_text(encoding="utf-8"))
                if (
                    not isinstance(gate, dict)
                    or set(gate) != {"blocked", "reason", "operation_ids"}
                    or gate.get("blocked") is not True
                    or not isinstance(gate.get("reason"), str)
                    or gate.get("reason")
                    not in {"operation_pending", "state_corrupt", "recovery_required"}
                    or not isinstance(gate.get("operation_ids"), list)
                    or any(
                        not isinstance(value, str) for value in gate["operation_ids"]
                    )
                ):
                    raise ValueError("invalid gate")
            except (OSError, ValueError):
                evidence = self.gate_path.with_name(
                    f"{self.gate_path.name}.corrupt.{uuid.uuid4().hex}"
                )
                os.replace(self.gate_path, evidence)
                gate_corrupt = True
        try:
            active = self._active_operations()
        except StateCorrupt:
            self._write_gate("state_corrupt", [])
            return
        if active:
            self._write_gate("operation_pending", active)
            return
        # A claim intent is deliberately journaled before the remote request.
        # Preserve its ordinary operation gate across restarts so the reporter
        # can reconcile that exact idempotent claim instead of converting it to
        # a generic recovery gate that blocks all reporting.
        if self.gate_path.exists() and gate.get("reason") == "operation_pending":
            operation_ids = gate["operation_ids"]
            with closing(self._connect()) as connection:
                pending_ids = [
                    row[0]
                    for row in connection.execute(
                        "SELECT d.operation_id FROM update_details d "
                        "JOIN operations o USING(operation_id) "
                        "WHERE o.phase='requested' AND d.phase='claim_pending' "
                        "ORDER BY d.operation_id"
                    ).fetchall()
                ]
            if operation_ids and sorted(operation_ids) == pending_ids:
                return
        if self.gate_path.exists() and gate.get("reason") != "state_corrupt":
            operation_ids = gate["operation_ids"]
            with closing(self._connect()) as connection:
                terminal = (
                    connection.execute(
                        "SELECT COUNT(*) FROM update_details WHERE operation_id IN ("
                        + ",".join("?" for _ in operation_ids)
                        + ") AND phase IN ('awaiting_confirmation','rolled_back','failed','expired')",
                        operation_ids,
                    ).fetchone()[0]
                    if operation_ids
                    else 0
                )
            if operation_ids and terminal == len(operation_ids):
                self._clear_gate()
                return
        if gate_corrupt:
            self._write_gate("state_corrupt", [])
        elif self.gate_path.exists() and gate["reason"] != "state_corrupt":
            self._write_gate("recovery_required", gate["operation_ids"])

    def serve(self) -> None:
        self.initialize()
        self.socket_path.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket = server
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(16)
        server.settimeout(1)
        self._notify(
            "READY=1\nSTATUS=Durable update journal restored; metadata checks only"
        )
        reporter = threading.Thread(target=self._report_pending_events, daemon=True)
        reporter.start()
        recovery = threading.Thread(target=self._resume_interrupted_update, daemon=True)
        recovery.start()
        while not self.stopping.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                if self.stopping.is_set():
                    break
                raise
            threading.Thread(
                target=self._handle_connection, args=(connection,), daemon=True
            ).start()
        self._stop_children()
        server.close()
        self.socket_path.unlink(missing_ok=True)

    def _report_pending_events(self) -> None:
        while not self.stopping.wait(self.report_retry_delay):
            if (self.state_dir / "reporting-paused-403").exists():
                return
            try:
                with closing(self._connect()) as db:
                    operations = [
                        row[0]
                        for row in db.execute(
                            "SELECT operation_id FROM update_details WHERE pending_event IS NOT NULL"
                        ).fetchall()
                    ]
                healthy = self._reconcile_pending_claims()
                for operation_id in operations:
                    healthy = self._flush_events(operation_id) and healthy
                if healthy:
                    self.report_retry_delay = 5
            except (sqlite3.DatabaseError, OSError, StateCorrupt):
                # Keep the durable event and retry on the next interval.
                self.report_retry_delay = min(
                    {5: 15, 15: 60, 60: 300}.get(self.report_retry_delay, 300), 300
                )
                continue

    def _handle_connection(self, connection: socket.socket) -> None:
        with connection:
            connection.settimeout(2)
            if not self._is_root_peer(connection):
                return
            data = bytearray()
            malformed = False
            while len(data) <= MAX_MESSAGE_BYTES:
                chunk = connection.recv(min(1024, MAX_MESSAGE_BYTES + 1 - len(data)))
                if not chunk:
                    break
                if b"\n" in chunk:
                    line, _, trailing = chunk.partition(b"\n")
                    data.extend(line)
                    malformed = bool(trailing)
                    break
                data.extend(chunk)
            response: dict[str, Any]
            if len(data) > MAX_MESSAGE_BYTES or malformed:
                response = {"ok": False, "error": "invalid_request"}
            else:
                try:
                    request = json.loads(data)
                    if not isinstance(request, dict) or "command" not in request:
                        raise ValueError
                    command = request["command"]
                    if command == "inspect":
                        if set(request) != {"command"}:
                            raise ValueError
                        response = self.inspect()
                    elif command == "check":
                        if set(request) != {"command"}:
                            raise ValueError
                        response = self.check()
                    elif command == "readiness":
                        response = self._readiness_handshake(connection, request)
                        connection.sendall(
                            json.dumps(response, separators=(",", ":")).encode()
                        )
                        return
                    elif command == "accept_update":
                        if set(request) != {
                            "command",
                            "update_id",
                            "session_id",
                            "release_id",
                            "target_package_version",
                            "sha256",
                            "expires_at",
                        }:
                            raise ValueError
                        response = self.accept_update(
                            {
                                key: value
                                for key, value in request.items()
                                if key != "command"
                            }
                        )
                    else:
                        response = {"ok": False, "error": "unsupported_command"}
                except (ValueError, TypeError, json.JSONDecodeError):
                    response = {"ok": False, "error": "invalid_request"}
                except StateCorrupt:
                    response = {"ok": False, "error": "state_corrupt"}
                except (OSError, subprocess.SubprocessError):
                    response = {"ok": False, "error": "metadata_check_failed"}
            payload = json.dumps(response, separators=(",", ":")).encode()
            connection.sendall(payload[:MAX_MESSAGE_BYTES])

    @staticmethod
    def _peer_credentials(connection: socket.socket) -> tuple[int, int] | None:
        if not hasattr(socket, "SO_PEERCRED"):
            return None
        credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        uid = int.from_bytes(credentials[4:8], byteorder=sys.byteorder, signed=True)
        pid = int.from_bytes(credentials[0:4], byteorder=sys.byteorder, signed=True)
        return uid, pid

    @classmethod
    def _is_root_peer(cls, connection: socket.socket) -> bool:
        credentials = cls._peer_credentials(connection)
        return credentials is not None and credentials[0] == 0

    @staticmethod
    def _systemd_agent_identity() -> tuple[int, str]:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                "dmitri-agent.service",
                "--property=MainPID,InvocationID",
                "--value",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.splitlines()
        if (
            len(lines) != 2
            or not lines[0].isdigit()
            or int(lines[0]) <= 0
            or not lines[1]
        ):
            raise OSError("agent systemd identity unavailable")
        return int(lines[0]), lines[1]

    @staticmethod
    def _installed_agent_package_version() -> str:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", "hardware-agent"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip()
        if not version:
            raise OSError("agent package version unavailable")
        return version

    @staticmethod
    def _installed_agent_app_version() -> str:
        result = subprocess.run(
            [
                "/opt/dmitri-agent/.venv/bin/python",
                "-c",
                "from agent.version import installed_version; "
                "print(installed_version())",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        value = result.stdout.strip()
        if not value:
            raise OSError("agent application version unavailable")
        return value

    def _readiness_handshake(
        self, connection: socket.socket, request: dict[str, Any]
    ) -> dict[str, Any]:
        if set(request) != {"command", "app_version", "package_version"}:
            return {"ok": False, "error": "invalid_request"}
        app_version = request["app_version"]
        package_version = request["package_version"]
        peer = self._peer_credentials(connection)
        if (
            peer is None
            or peer[0] != 0
            or not isinstance(app_version, str)
            or not isinstance(package_version, str)
        ):
            return {"ok": False, "error": "stale_session"}
        try:
            pid, invocation = self.readiness_identity()
            if (
                peer[1] != pid
                or self.package_version() != package_version
                or self.app_version() != app_version
            ):
                return {"ok": False, "error": "stale_session"}
            nonce = secrets.token_hex(24)
            connection.sendall(
                json.dumps(
                    {
                        "nonce": nonce,
                        "main_pid": pid,
                        "invocation_id": invocation,
                    },
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
            response = bytearray()
            while len(response) <= MAX_MESSAGE_BYTES:
                chunk = connection.recv(MAX_MESSAGE_BYTES + 1 - len(response))
                if not chunk:
                    return {"ok": False, "error": "stale_session"}
                if b"\n" in chunk:
                    line, _, trailing = chunk.partition(b"\n")
                    if trailing:
                        return {"ok": False, "error": "invalid_request"}
                    response.extend(line)
                    break
                response.extend(chunk)
            evidence = json.loads(response)
            if not isinstance(evidence, dict) or set(evidence) != {
                "nonce",
                "main_pid",
                "invocation_id",
                "app_version",
                "package_version",
            }:
                return {"ok": False, "error": "invalid_request"}
            if evidence != {
                "nonce": nonce,
                "main_pid": pid,
                "invocation_id": invocation,
                "app_version": app_version,
                "package_version": package_version,
            } or self.readiness_identity() != (pid, invocation):
                return {"ok": False, "error": "stale_session"}
            self.last_readiness = (pid, invocation, app_version, package_version)
            return {
                "ok": True,
                "main_pid": pid,
                "invocation_id": invocation,
                "app_version": app_version,
                "package_version": package_version,
                "nonce": nonce,
            }
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            return {"ok": False, "error": "stale_session"}

    def inspect(self) -> dict[str, Any]:
        try:
            active = self._active_operations()
        except StateCorrupt:
            self._write_gate("state_corrupt", [])
            raise
        return {
            "ok": True,
            "capabilities": ["inspect", "check"],
            "blocked": bool(active)
            or self.gate_path.exists()
            or self.scan_checkpoint_path.exists(),
        }

    def check(self) -> dict[str, Any]:
        if self.stopping.is_set():
            return {"ok": False, "error": "supervisor_stopping"}
        try:
            if (
                self._active_operations()
                or self.gate_path.exists()
                or self.scan_checkpoint_path.exists()
            ):
                return {"ok": False, "error": "device_busy"}
        except StateCorrupt:
            self._write_gate("state_corrupt", [])
            return {"ok": False, "error": "state_corrupt"}
        descriptor = os.open(self.mutex_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"ok": False, "error": "device_busy"}
            try:
                if self._active_operations() or self.gate_path.exists():
                    return {"ok": False, "error": "device_busy"}
            except StateCorrupt:
                self._write_gate("state_corrupt", [])
                return {"ok": False, "error": "state_corrupt"}
            result = self._run_metadata_refresh()
            if result:
                return {"ok": True, "metadata_refreshed": True}
            return {"ok": False, "error": "metadata_check_failed"}
        finally:
            os.close(descriptor)

    def accept_update(self, request: dict[str, Any]) -> dict[str, Any]:
        """Claim and apply one verified, cached package; all effects use fixed argv."""
        required = {
            "update_id",
            "session_id",
            "release_id",
            "target_package_version",
            "sha256",
            "expires_at",
        }
        if set(request) != required or not all(
            isinstance(request[k], str) for k in required
        ):
            return {"ok": False, "error": "invalid_request"}
        try:
            update_id = str(uuid.UUID(request["update_id"]))
            session_id = str(uuid.UUID(request["session_id"]))
            release_id = str(uuid.UUID(request["release_id"]))
            target_version = request["target_package_version"]
            digest = request["sha256"]
            deadline = datetime.fromisoformat(
                request["expires_at"].replace("Z", "+00:00")
            )
            if (
                len(target_version) > 128
                or not target_version
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError
            if deadline.tzinfo is None or datetime.now(timezone.utc) >= deadline:
                return {"ok": False, "error": "authorization_expired"}
        except (ValueError, TypeError, AttributeError):
            return {"ok": False, "error": "invalid_request"}
        if (
            self.stopping.is_set()
        ):
            return {"ok": False, "error": "device_busy"}
        lock_fd = os.open(self.mutex_path, os.O_RDWR | os.O_CREAT, 0o600)
        scan_fd = -1
        try:
            import fcntl

            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"ok": False, "error": "device_busy"}
            try:
                import fcntl
                path = Path(SCAN_LOCK_PATH_FILE.read_text(encoding="ascii").strip())
                if path != SCAN_LOCK_PATH:
                    raise OSError("invalid scan lock contract")
                scan_fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
                fcntl.flock(scan_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, BlockingIOError):
                if scan_fd >= 0:
                    os.close(scan_fd)
                return {"ok": False, "error": "device_busy"}
            # These mutable preconditions must be re-read while both exclusion
            # locks are held; a scan/checkpoint may have started after the first
            # fast-path check above.
            if self.gate_path.exists() or self.scan_checkpoint_path.exists():
                return {"ok": False, "error": "device_busy"}
            try:
                if self._active_operations():
                    return {"ok": False, "error": "device_busy"}
            except StateCorrupt:
                self._write_gate("state_corrupt", [])
                return {"ok": False, "error": "state_corrupt"}
            return self._apply_claimed_update(
                update_id, session_id, release_id, target_version, digest, deadline
            )
        finally:
            if scan_fd >= 0:
                os.close(scan_fd)
            os.close(lock_fd)

    def _apply_claimed_update(
        self,
        update_id: str,
        session_id: str,
        release_id: str,
        target: str,
        digest: str,
        deadline: datetime,
    ) -> dict[str, Any]:
        with closing(self._connect()) as db:
            existing = db.execute(
                "SELECT phase FROM update_details WHERE operation_id=?",
                (update_id,),
            ).fetchone()
        if existing:
            return {"ok": True, "phase": existing[0], "replayed": True}
        package = PACKAGE_CACHE / f"{digest}.deb"
        try:
            # Refresh and validate signed repository evidence even on cache hits:
            # a local file alone is not proof of current release authorization.
            if not self._run_metadata_refresh():
                raise UpdateFailure("metadata_untrusted")
            _verify_apt_origin_suite(target, digest)
            if not package.is_file() or _sha256(package) != digest:
                package = _download_trusted_package(target, digest)
        except Exception as exc:
            return {"ok": False, "error": _failure_code(exc)}
        if not package.is_file() or _sha256(package) != digest:
            return {"ok": False, "error": "artifact_unavailable"}
        try:
            _verify_package(package, target)
            prior = self.package_version()
            # The trusted previously-installed package must already be cached and verified.
            previous = PACKAGE_CACHE / (prior + ".deb")
            if not previous.is_file():
                return {"ok": False, "error": "previous_package_unavailable"}
            _verify_cache_digest(previous, prior)
            _verify_package(previous, prior)
            _preflight(package, prior, target)
            _cache_versioned_package(package, target)
            if datetime.now(timezone.utc) >= deadline:
                self._record_expired(update_id, session_id, release_id, target, digest, deadline)
                return {"ok": False, "error": "authorization_expired"}
            # Record the idempotent claim intent before contacting the backend.
            with closing(self._connect()) as db, db:
                db.execute("INSERT OR IGNORE INTO operations VALUES (?, 'requested')", (update_id,))
                db.execute("INSERT OR IGNORE INTO update_details(operation_id,session_id,release_id,target_version,sha256,deadline,prior_version,phase) VALUES(?,?,?,?,?,?,?,'claim_pending')", (update_id, session_id, release_id, target, digest, deadline.isoformat(), prior))
            claim = self._post_json(
                f"/api/v1/agent-updates/{update_id}/claim",
                {
                    "session_id": session_id,
                    "release_id": release_id,
                    "target_package_version": target,
                    "sha256": digest,
                },
            )
            if not _claim_receipt_matches(
                claim, digest, target,
                update_id=update_id, session_id=session_id, release_id=release_id,
            ):
                self._emit(
                    update_id, session_id, "failed", "failed", None,
                    error="artifact_mismatch",
                )
                return {"ok": False, "error": "claim_mismatch"}
            deadline = datetime.fromisoformat(
                claim["authorization_deadline"].replace("Z", "+00:00")
            )
            snapshot = self.state_dir / f"snapshot-{update_id}"
            if (
                AGENT_ROOT.exists()
                and AGENT_ROOT.stat().st_dev != self.state_dir.stat().st_dev
            ):
                raise UpdateFailure("snapshot_filesystem_mismatch")
            with closing(self._connect()) as db, db:
                db.execute("UPDATE operations SET phase='preparing' WHERE operation_id=?", (update_id,))
                db.execute("UPDATE update_details SET deadline=?,snapshot=?,phase='preparing' WHERE operation_id=?", (deadline.isoformat(), str(snapshot), update_id))
            self._write_gate("operation_pending", [update_id])
            self._emit(update_id, session_id, "preparing", None, None)
            if datetime.now(timezone.utc) >= deadline:
                self._expire_before_mutation(update_id, session_id)
                self._clear_gate()
                return {"ok": False, "error": "authorization_expired"}
            if AGENT_ROOT.exists():
                shutil.copytree(AGENT_ROOT, snapshot, symlinks=True)
                _fsync_tree(snapshot)
                _fsync_directory(snapshot.parent)
            if datetime.now(timezone.utc) >= deadline:
                self._expire_before_mutation(update_id, session_id)
                self._clear_gate()
                return {"ok": False, "error": "authorization_expired"}
            # The backend's accepted installing event is the transaction
            # boundary. If the deadline expires while reporting or stopping the
            # service, perform safety recovery and never start dpkg afterward.
            self._emit(update_id, session_id, "installing", None, None)
            _systemctl("stop", "dmitri-agent.service")
            if datetime.now(timezone.utc) >= deadline:
                raise UpdateFailure("authorization_expired")
            self._run_checked(
                ["/usr/bin/dpkg", "--install", str(package)],
                timeout=1800,
            )
            self._emit(update_id, session_id, "verifying", None, None)
            with closing(self._connect()) as db, db:
                db.execute(
                    "UPDATE operations SET phase='verifying' WHERE operation_id=?",
                    (update_id,),
                )
                db.execute(
                    "UPDATE update_details SET phase='verifying' WHERE operation_id=?",
                    (update_id,),
                )
            invocation = self._verify_local_health(target)
            self._emit(
                update_id, session_id, "awaiting_confirmation", "succeeded", invocation
            )
            self._clear_gate()
            return {"ok": True, "phase": "awaiting_confirmation"}
        except Exception as exc:
            with closing(self._connect()) as db:
                detail = db.execute(
                    "SELECT phase FROM update_details WHERE operation_id=?",
                    (update_id,),
                ).fetchone()
            if detail is None:
                code = _failure_code(exc)
                try:
                    self._post_json(
                        f"/api/v1/agent-updates/{update_id}/events",
                        {
                            "sequence": 1,
                            "phase": "failed",
                            "local_outcome": "failed",
                            "observed_version": None,
                            "package_version": self.package_version(),
                            "invocation_id": None,
                            "session_id": session_id,
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                            "error_code": _failure_code(exc),
                            "evidence": None,
                        },
                    )
                except Exception:
                    pass
                return {"ok": False, "error": code}
            if detail[0] == "claim_pending":
                # Reporter/startup reconciliation will retry the idempotent claim.
                return {"ok": False, "error": "claim_pending"}
            return self._recover_update(update_id, session_id, str(exc))

    def _expire_before_mutation(self, update_id: str, session_id: str) -> None:
        self._emit(
            update_id,
            session_id,
            "expired",
            None,
            None,
            error="request_expired",
        )

    def _run_checked(self, argv: list[str], *, timeout: int) -> str:
        with self.child_lock:
            if self.stopping.is_set():
                raise UpdateFailure("updater_stopping")
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={
                    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                    "DEBIAN_FRONTEND": "noninteractive",
                    "LANG": "C.UTF-8",
                },
                start_new_session=True,
            )
            self.children.add(process)
        try:
            stdout, _stderr = process.communicate(timeout=timeout)
            if process.returncode:
                raise subprocess.CalledProcessError(
                    process.returncode, argv, output=stdout
                )
            return stdout.strip()
        except subprocess.TimeoutExpired as exc:
            # dpkg must never be killed mid-database transaction. Keep the gate
            # and wait for its supervised completion; bounded health/query tools
            # are terminated as a process group and can safely fail closed.
            if Path(argv[0]).name == "dpkg":
                self._write_gate("operation_pending", self._active_operation_ids())
                process.communicate()
                raise UpdateFailure("package_command_still_running") from exc
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                process.communicate()
            raise UpdateFailure("package_command_timeout") from exc
        finally:
            with self.child_lock:
                self.children.discard(process)

    def _active_operation_ids(self) -> list[str]:
        with closing(self._connect()) as db:
            return [
                row[0]
                for row in db.execute(
                    "SELECT operation_id FROM operations WHERE phase IN ('preparing','installing','verifying','recovering')"
                ).fetchall()
            ]

    def _record_expired(self, update_id: str, session_id: str, release_id: str, target: str, digest: str, deadline: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO operations VALUES (?, 'preparing')", (update_id,))
            db.execute("INSERT OR IGNORE INTO update_details(operation_id,session_id,release_id,target_version,sha256,deadline,phase) VALUES(?,?,?,?,?,?, 'preparing')", (update_id, session_id, release_id, target, digest, deadline.isoformat()))
        self._emit(update_id, session_id, "expired", "expired", None, error="request_expired")

    def _resume_interrupted_update(self) -> None:
        """Reconcile one journaled package transaction before agent startup."""
        with closing(self._connect()) as db:
            pending = db.execute(
                "SELECT 1 FROM update_details d JOIN operations o USING(operation_id) "
                "WHERE o.phase IN ('preparing','installing','verifying','recovering') "
                "OR (o.phase='requested' AND d.phase='claim_pending') LIMIT 1"
            ).fetchone()
        if not pending:
            return
        # Recovery changes the installed tree just like a new install. Keep both
        # exclusion locks until all local recovery and durable reporting is done.
        with self._exclusive_update_locks():
            self._resume_interrupted_update_locked()

    @contextmanager
    def _exclusive_update_locks(self):
        import fcntl

        mutex_fd = os.open(self.mutex_path, os.O_RDWR | os.O_CREAT, 0o600)
        scan_fd = -1
        try:
            fcntl.flock(mutex_fd, fcntl.LOCK_EX)
            lock_path = Path(SCAN_LOCK_PATH_FILE.read_text(encoding="ascii").strip())
            if lock_path != SCAN_LOCK_PATH:
                raise OSError("invalid scan lock contract")
            scan_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(scan_fd, fcntl.LOCK_EX)
            yield
        finally:
            if scan_fd >= 0:
                os.close(scan_fd)
            os.close(mutex_fd)

    def _resume_interrupted_update_locked(self) -> None:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT d.operation_id,d.session_id,d.target_version,d.phase,d.recovery_attempts,d.release_id,d.sha256 "
                "FROM update_details d JOIN operations o USING(operation_id) "
                "WHERE o.phase IN ('preparing','installing','verifying','recovering') OR (o.phase='requested' AND d.phase='claim_pending') "
                "ORDER BY d.operation_id"
            ).fetchall()
        for update_id, session_id, target, phase, recovery_attempts, release_id, digest in rows:
            if phase == "claim_pending":
                self._reconcile_claim_locked(
                    update_id, session_id, target, release_id, digest
                )
                continue
            if phase == "preparing":
                self._recover_update(update_id, session_id, "interrupted_before_install")
                continue
            if phase == "recovering" and recovery_attempts:
                self._needs_intervention(update_id, session_id)
                continue
            try:
                if self.package_version() != target:
                    raise UpdateFailure("install_failed")
                invocation = self._verify_local_health(target)
                if phase == "installing":
                    self._emit(update_id, session_id, "verifying", None, None)
                self._emit(
                    update_id,
                    session_id,
                    "awaiting_confirmation",
                    "succeeded",
                    invocation,
                )
                self._clear_gate()
            except Exception as exc:
                self._recover_update(update_id, session_id, str(exc))

    def _reconcile_pending_claims(self) -> bool:
        """Retry durable idempotent claims while preserving update/scan exclusion."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT d.operation_id,d.session_id,d.target_version,d.release_id,d.sha256 "
                "FROM update_details d JOIN operations o USING(operation_id) "
                "WHERE o.phase='requested' AND d.phase='claim_pending'"
            ).fetchall()
        if not rows:
            return True
        try:
            with self._exclusive_update_locks():
                if self.scan_checkpoint_path.exists():
                    return False
                if self.gate_path.exists():
                    try:
                        gate = json.loads(self.gate_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        return False
                    pending_ids = sorted(row[0] for row in rows)
                    gate_ids = gate.get("operation_ids") if isinstance(gate, dict) else None
                    if (
                        not isinstance(gate, dict)
                        or gate.get("blocked") is not True
                        or gate.get("reason") != "operation_pending"
                        or not isinstance(gate_ids, list)
                        or any(not isinstance(value, str) for value in gate_ids)
                        or sorted(gate_ids) != pending_ids
                    ):
                        return False
                if self._active_operations() != [row[0] for row in rows]:
                    # A pending update itself is expected; any other operation
                    # makes this retry unsafe.
                    active = set(self._active_operations())
                    if active - {row[0] for row in rows}:
                        return False
                for update_id, session_id, target, release_id, digest in rows:
                    if not self._reconcile_claim_locked(
                        update_id, session_id, target, release_id, digest
                    ):
                        return False
                return True
        except (OSError, BlockingIOError, StateCorrupt):
            return False

    def _reconcile_claim_locked(
        self, update_id: str, session_id: str, target: str, release_id: str, digest: str
    ) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT deadline FROM update_details WHERE operation_id=? AND phase='claim_pending'",
                (update_id,),
            ).fetchone()
        if row is None:
            return True
        try:
            claim_deadline = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            if claim_deadline.tzinfo is None:
                raise ValueError("timezone required")
        except (AttributeError, TypeError, ValueError):
            return False
        try:
            claim = self._post_json(
                f"/api/v1/agent-updates/{update_id}/claim",
                {
                    "session_id": session_id,
                    "release_id": release_id,
                    "target_package_version": target,
                    "sha256": digest,
                },
            )
        except Exception as exc:
            # Only the backend's explicit 410 request_expired response proves
            # that no claim was admitted. A lost response or 409 can mean the
            # claim committed; retain and retry the same idempotency key.
            if _is_expired_claim_response(exc):
                with closing(self._connect()) as db, db:
                    db.execute(
                        "UPDATE update_details SET phase='expired' WHERE operation_id=? AND phase='claim_pending'",
                        (update_id,),
                    )
                    db.execute(
                        "UPDATE operations SET phase='expired' WHERE operation_id=? AND phase='requested'",
                        (update_id,),
                    )
                self._remove_from_operation_gate(update_id)
                return True
            self.report_retry_delay = min(
                {5: 15, 15: 60, 60: 300}.get(self.report_retry_delay, 300), 300
            )
            return False
        if not _claim_receipt_matches(
            claim, digest, target,
            update_id=update_id, session_id=session_id, release_id=release_id,
        ):
            # Report a terminal pre-mutation rejection. If the backend cannot
            # accept it yet, _emit retains the durable event for retry.
            self._emit(
                update_id, session_id, "failed", "failed", None,
                error="artifact_mismatch",
            )
            return True
        try:
            authorization_deadline = datetime.fromisoformat(
                claim["authorization_deadline"].replace("Z", "+00:00")
            )
            if authorization_deadline.tzinfo is None:
                raise ValueError("timezone required")
        except (KeyError, TypeError, ValueError):
            self.report_retry_delay = min(
                {5: 15, 15: 60, 60: 300}.get(self.report_retry_delay, 300), 300
            )
            return False
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE update_details SET phase='preparing',deadline=? WHERE operation_id=? AND phase='claim_pending'",
                (authorization_deadline.isoformat(), update_id),
            )
            db.execute(
                "UPDATE operations SET phase='preparing' WHERE operation_id=? AND phase='requested'",
                (update_id,),
            )
        # The interrupted process cannot prove that its preflight artifacts and
        # snapshot survived. End the admitted operation safely before mutation.
        self._recover_update(update_id, session_id, "interrupted_before_install")
        return True

    def _needs_intervention(self, update_id: str, session_id: str) -> None:
        self._write_gate("recovery_required", [update_id])
        try:
            self._emit(
                update_id,
                session_id,
                "needs_intervention",
                "needs_intervention",
                None,
                error="recovery_failed",
            )
        except Exception:
            pass

    def _verify_local_health(self, target: str) -> str:
        expected_app_version = _application_version_for_package(target)
        dpkg = self._run_checked(
            ["/usr/bin/dpkg-query", "-W", "-f=${Status}", "hardware-agent"], timeout=10
        )
        if dpkg != "install ok installed" or self.package_version() != target:
            raise UpdateFailure("local_health_failed")
        health = self._run_checked(
            ["/opt/dmitri-agent/.venv/bin/dmitri", "health", "--json"], timeout=30
        )
        health_report = json.loads(health)
        app_version = self.app_version()
        if (
            health_report.get("ok") is not True
            or health_report.get("version") != expected_app_version
            or app_version != expected_app_version
        ):
            raise UpdateFailure("local_health_failed")
        # A daemon may already have completed its one-shot readiness handshake
        # after starting against this updater. Reuse it only when it still binds
        # the currently running process and exact target package/application;
        # an old-version handshake cannot satisfy these checks.
        _systemctl("start", "dmitri-agent.service")
        for _ in range(30):
            try:
                pid, invocation = self.readiness_identity()
                if self.last_readiness == (
                    pid,
                    invocation,
                    expected_app_version,
                    self.package_version(),
                ):
                    break
            except (OSError, subprocess.SubprocessError):
                pass
            time.sleep(1)
        else:
            raise UpdateFailure("local_health_failed")
        return invocation

    def _recover_update(
        self, update_id: str, session_id: str, reason: str
    ) -> dict[str, Any]:
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT prior_version,snapshot,phase FROM update_details WHERE operation_id=?",
                    (update_id,),
                ).fetchone()
            if row is not None and row[2] == "preparing":
                _systemctl("start", "dmitri-agent.service")
                self._emit(
                    update_id,
                    session_id,
                    "failed",
                    "failed",
                    None,
                    error=_failure_code(UpdateFailure(reason)),
                )
                self._clear_gate()
                return {"ok": False, "error": "preflight_failed"}
            if row is None or row[0] is None or not row[1]:
                raise UpdateFailure("recovery_unavailable")
            prior, snapshot, _phase = row
            with closing(self._connect()) as db, db:
                attempt = db.execute(
                    "SELECT recovery_attempts FROM update_details WHERE operation_id=?",
                    (update_id,),
                ).fetchone()[0]
                if attempt:
                    raise UpdateFailure("recovery_already_attempted")
                db.execute(
                    "UPDATE update_details SET phase='recovering',recovery_attempts=1,error_code=? WHERE operation_id=?",
                    (_failure_code(UpdateFailure(reason)), update_id),
                )
                db.execute(
                    "UPDATE operations SET phase='recovering' WHERE operation_id=?",
                    (update_id,),
                )
            self._emit(
                update_id,
                session_id,
                "recovering",
                None,
                None,
                error=_failure_code(UpdateFailure(reason)),
            )
            _systemctl("stop", "dmitri-agent.service")
            old_package = PACKAGE_CACHE / (prior + ".deb")
            if not old_package.is_file():
                raise UpdateFailure("recovery_package_missing")
            _verify_cache_digest(old_package, prior)
            _verify_package(old_package, prior)
            self._run_checked(
                [
                    "/usr/bin/dpkg",
                    "--force-downgrade",
                    "--install",
                    str(old_package),
                ],
                timeout=1800,
            )
            if AGENT_ROOT.exists():
                shutil.rmtree(AGENT_ROOT)
            shutil.copytree(snapshot, AGENT_ROOT, symlinks=True)
            _fsync_tree(AGENT_ROOT)
            _fsync_directory(AGENT_ROOT.parent)
            invocation = self._verify_local_health(prior)
            with closing(self._connect()) as db:
                original_error = db.execute(
                    "SELECT error_code FROM update_details WHERE operation_id=?",
                    (update_id,),
                ).fetchone()[0]
            self._emit(
                update_id,
                session_id,
                "rolled_back",
                "rolled_back",
                invocation,
                error=original_error or "install_failed",
            )
            self._clear_gate()
            return {"ok": False, "error": "rolled_back"}
        except Exception:
            self._needs_intervention(update_id, session_id)
            return {"ok": False, "error": "needs_intervention"}

    def _emit(
        self,
        update_id: str,
        session_id: str,
        phase: str,
        outcome: str | None,
        invocation: str | None,
        error: str | None = None,
    ) -> None:
        with closing(self._connect()) as db, db:
            detail = db.execute(
                "SELECT sequence,deadline,target_version FROM update_details WHERE operation_id=?",
                (update_id,),
            ).fetchone()
            seq = detail[0] + 1
            body = {
                "sequence": seq,
                "phase": phase,
                "local_outcome": outcome,
                "observed_version": self.app_version()
                if outcome in {"succeeded", "rolled_back"}
                else None,
                "package_version": self.package_version(),
                "invocation_id": invocation,
                "session_id": session_id,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "error_code": error,
                "evidence": {
                    "package_status": "configured",
                    "service_active": True,
                    "health_check": "passed",
                }
                if outcome in {"succeeded", "rolled_back"}
                else None,
            }
            encoded = json.dumps(body, separators=(",", ":"), sort_keys=True)
            db.execute(
                "INSERT INTO update_events VALUES(?,?,?)", (update_id, seq, encoded)
            )
            db.execute(
                "UPDATE update_details SET sequence=?,pending_event=COALESCE(pending_event,?),phase=?,invocation_id=? WHERE operation_id=?",
                (seq, encoded, phase, invocation, update_id),
            )
            operation_phase = "succeeded" if phase == "awaiting_confirmation" else phase
            db.execute(
                "UPDATE operations SET phase=? WHERE operation_id=?",
                (operation_phase, update_id),
            )
        self._flush_events(update_id)

    def _flush_events(self, update_id: str) -> bool:
        if (self.state_dir / "reporting-paused-403").exists():
            return False
        while True:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT ack_sequence,sequence FROM update_details WHERE operation_id=?",
                    (update_id,),
                ).fetchone()
                event = db.execute(
                    "SELECT sequence,body FROM update_events WHERE operation_id=? AND sequence>? ORDER BY sequence LIMIT 1",
                    (update_id, row[0] if row else 0),
                ).fetchone()
            if not row or not event:
                return True
            event_sequence, event_body = event
            body = json.loads(event_body)
            try:
                ack = self._post_json(f"/api/v1/agent-updates/{update_id}/events", body)
            except Exception as exc:
                self.report_retry_delay = min(
                    {5: 15, 15: 60, 60: 300}.get(self.report_retry_delay, 300), 300
                )
                if getattr(exc, "code", None) == 403 or "403" in str(exc):
                    pause = self.state_dir / "reporting-paused-403"
                    with pause.open("a", encoding="ascii") as marker:
                        marker.write("paused\n")
                        marker.flush()
                        os.fsync(marker.fileno())
                    _fsync_directory(pause.parent)
                return False
            if ack.get("ack_sequence") != event_sequence:
                self.report_retry_delay = min(
                    {5: 15, 15: 60, 60: 300}.get(self.report_retry_delay, 300), 300
                )
                return False
            with closing(self._connect()) as db, db:
                db.execute(
                    "UPDATE update_details SET ack_sequence=?,pending_event=(SELECT body FROM update_events WHERE operation_id=? AND sequence=?) WHERE operation_id=?",
                    (event_sequence, update_id, event_sequence + 1, update_id),
                )
            with closing(self._connect()) as db:
                db.execute("PRAGMA wal_checkpoint(FULL)")

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        import importlib.util
        from urllib.parse import urlsplit
        from urllib.request import Request, urlopen

        values = _read_env(AGENT_ENV)
        key = bytes.fromhex(values["DEVICE_PRIVATE_KEY"])
        device = values["DEVICE_ID"]
        base = values["BACKEND_URL"].rstrip("/")
        if urlsplit(base).scheme != "https":
            raise ValueError("HTTPS required for update reports")
        payload = json.dumps(body, separators=(",", ":")).encode()
        signer_path = Path("/usr/lib/dmitri/device_signing.py")
        spec = importlib.util.spec_from_file_location(
            "dmitri_device_signing", signer_path
        )
        if spec is None or spec.loader is None:
            raise OSError("device signer unavailable")
        signer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(signer)
        headers = signer.build_device_signature_headers(
            "POST", path, payload, device, key
        )
        headers["Content-Type"] = "application/json"
        request = Request(base + path, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=20) as response:
            if response.status < 200 or response.status >= 300:
                raise OSError("update report rejected")
            data = json.loads(response.read(65537))
        if not isinstance(data, dict):
            raise ValueError("invalid update response")
        return data

    def _run_metadata_refresh(self) -> bool:
        with self.child_lock:
            if self.stopping.is_set():
                return False
            process = subprocess.Popen(
                ["/usr/bin/apt-get", "-o", "APT::Update::Error-Mode=any", "update"],
                stdin=subprocess.DEVNULL,
                env={
                    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                    "DEBIAN_FRONTEND": "noninteractive",
                    "LANG": "C.UTF-8",
                },
                start_new_session=True,
            )
            self.children.add(process)
        try:
            try:
                return process.wait(timeout=CHECK_TIMEOUT_SECONDS) == 0
            except subprocess.TimeoutExpired:
                self._terminate_process(process)
                return False
        finally:
            with self.child_lock:
                self.children.discard(process)

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

    def _stop_children(self) -> None:
        with self.child_lock:
            children = list(self.children)
        for child in children:
            self._terminate_process(child)

    @staticmethod
    def _notify(message: str) -> None:
        address = os.environ.get("NOTIFY_SOCKET")
        if not address:
            return
        if address.startswith("@"):
            address = "\0" + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notification:
            notification.connect(address)
            notification.sendall(message.encode())

    def stop(self, *_: object) -> None:
        self.stopping.set()
        if self.server_socket is not None:
            self.server_socket.close()
        self._stop_children()


def request(command: str, socket_path: Path = SOCKET_PATH) -> dict[str, Any]:
    if command not in {"inspect", "check"}:
        raise ValueError("unsupported command")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(CLIENT_TIMEOUT_SECONDS)
        client.connect(str(socket_path))
        payload = json.dumps({"command": command}, separators=(",", ":")).encode()
        client.sendall(payload + b"\n")
        response = client.recv(MAX_MESSAGE_BYTES + 1)
    if len(response) > MAX_MESSAGE_BYTES:
        raise ValueError("invalid response")
    parsed = json.loads(response)
    if not isinstance(parsed, dict):
        raise ValueError("invalid response")
    return parsed


class UpdateFailure(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        if path.is_file():
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        elif path.is_dir() and os.name == "posix":
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    if os.name == "posix":
        _fsync_directory(root)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _verify_package(package: Path, expected_version: str) -> None:
    result = subprocess.run(
        ["/usr/bin/dpkg-deb", "-f", str(package), "Package", "Version", "Architecture"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    fields = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    if fields != {"Package": "hardware-agent", "Version": expected_version, "Architecture": "arm64"}:
        raise UpdateFailure("package_identity_mismatch")


def _verify_cache_digest(package: Path, version: str) -> None:
    manifest = PACKAGE_CACHE / f"{version}.sha256"
    try:
        expected = manifest.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise UpdateFailure("previous_package_unavailable") from exc
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise UpdateFailure("cache_manifest_invalid")
    if _sha256(package) != expected:
        raise UpdateFailure("cached_package_hash_mismatch")


def _download_trusted_package(version: str, expected_digest: str) -> Path:
    """Download only the fixed package/version from the configured signed APT repo."""
    if not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", version):
        raise UpdateFailure("metadata_untrusted")
    _verify_apt_origin_suite(version, expected_digest)
    PACKAGE_CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = PACKAGE_CACHE / f".download-{uuid.uuid4().hex}"
    staging.mkdir(mode=0o700)
    try:
        subprocess.run(
            ["/usr/bin/apt-get", "download", f"hardware-agent={version}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=staging,
            env={
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "DEBIAN_FRONTEND": "noninteractive",
                "LANG": "C.UTF-8",
            },
        )
        downloads = list(staging.glob("*.deb"))
        if len(downloads) != 1 or _sha256(downloads[0]) != expected_digest:
            raise UpdateFailure("artifact_mismatch")
        _verify_package(downloads[0], version)
        final = PACKAGE_CACHE / f"{expected_digest}.deb"
        os.replace(downloads[0], final)
        _fsync_directory(PACKAGE_CACHE)
        return final
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _verify_apt_origin_suite(version: str, expected_digest: str | None = None) -> None:
    """Bind the exact release and optional package digest to the provisioned APT source."""
    uri, _keyring = _verify_dedicated_apt_source()
    _verify_apt_metadata_dates(uri)
    result = subprocess.run(
        ["/usr/bin/apt-cache", "policy", "hardware-agent"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    )
    lines = result.stdout.splitlines()
    version_found = False
    trusted_version = False
    active_version = False
    active_uri = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Candidate:"):
            if stripped.split(":", 1)[1].strip() == version:
                version_found = True
        version_row = re.match(r"^([^\s]+)\s+\d+(?:\s|$)", stripped)
        if version_row:
            active_version = version_row.group(1) == version
            active_uri = False
            if version_row.group(1) == version:
                version_found = True
        elif active_version:
            source_match = re.match(
                r"^\d+\s+(https://\S+)\s+stable/main\s+\S+\s+Packages$",
                stripped,
            )
            if source_match:
                active_uri = source_match.group(1).rstrip("/") == uri.rstrip("/")
                if active_uri:
                    # Origin and Suite were checked in the APT-verified InRelease.
                    trusted_version = True
    if not version_found:
        raise UpdateFailure("metadata_unavailable")
    if not trusted_version:
        raise UpdateFailure("metadata_untrusted")
    if expected_digest is not None:
        record = _trusted_apt_package_record(version, uri)
        if record is None or not _apt_record_matches(
            record, version, expected_digest
        ):
            raise UpdateFailure("artifact_mismatch")


def _trusted_apt_package_record(version: str, source_uri: str) -> str | None:
    """Read the package record only from the Packages index at the pinned URI.

    apt's index target list maps each authenticated index file back to its
    source URI. `apt-helper cat-file` handles APT's compressed list formats.
    This avoids accepting a same-version/same-hash record from another origin.
    """
    index_targets = subprocess.run(
        [
            "/usr/bin/apt-get",
            "indextargets",
            "--format=$(URI)|$(FILENAME)|$(IDENTIFIER)|$(RELEASE)|$(COMPONENT)|$(ARCHITECTURE)",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    )
    expected_uri = source_uri.rstrip("/") + "/dists/stable/main/binary-arm64/Packages"
    index_files: list[Path] = []
    for line in index_targets.stdout.splitlines():
        parts = line.split("|", 5)
        if len(parts) != 6:
            continue
        uri, filename, identifier, release, component, architecture = parts
        if (
            uri.rstrip("/") == expected_uri
            and identifier == "Packages"
            and release == "stable"
            and component == "main"
            and architecture == "arm64"
        ):
            path = Path(filename)
            try:
                path.resolve(strict=True).relative_to(APT_LIST_DIR.resolve(strict=True))
            except (OSError, ValueError):
                continue
            if not path.is_symlink() and path.is_file():
                index_files.append(path)
    if len(index_files) != 1:
        return None
    content = subprocess.run(
        ["/usr/lib/apt/apt-helper", "cat-file", str(index_files[0])],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    ).stdout
    for record in re.split(r"\n\s*\n", content):
        if not record.strip():
            continue
        fields = {}
        for field_line in record.splitlines():
            key, separator, value = field_line.partition(":")
            if separator and not field_line[:1].isspace():
                fields[key.strip()] = value.strip()
        if fields.get("Package") == "hardware-agent" and fields.get("Version") == version:
            return record
    return None


def _verify_dedicated_apt_source() -> tuple[str, str]:
    """Require one enabled HTTPS stable source pinned to a root-owned keyring."""
    from urllib.parse import urlsplit

    source_files = [APT_SOURCE_LIST, *APT_SOURCE_DIR.glob("*.sources"), *APT_SOURCE_DIR.glob("*.list")]
    candidates: list[tuple[str, str, Path]] = []
    for source_file in source_files:
        try:
            content = source_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if source_file.suffix == ".sources":
            for stanza in re.split(r"\n\s*\n", content):
                fields = {}
                for line in stanza.splitlines():
                    if line[:1].isspace() or not line.strip() or line.lstrip().startswith("#"):
                        continue
                    key, separator, value = line.partition(":")
                    if separator:
                        fields[key.strip().lower()] = value.strip()
                if "no" in fields.get("enabled", "yes").lower():
                    continue
                uris = fields.get("uris", "").split()
                suites = fields.get("suites", "").split()
                keyring = fields.get("signed-by", "")
                options = " ".join(
                    value
                    for key, value in fields.items()
                    if key.lower().startswith(("trusted", "allow-insecure", "allow-weak", "check-valid-until"))
                ).lower()
                if any(value in options for value in ("yes", "true", "no")):
                    raise UpdateFailure("metadata_untrusted")
                if fields.get("check-valid-until", "yes").lower() in {"no", "false"}:
                    raise UpdateFailure("metadata_untrusted")
                for uri in uris:
                    parsed = urlsplit(uri)
                    if (
                        parsed.scheme == "https"
                        and parsed.hostname
                        and not parsed.username
                        and not parsed.password
                        and not parsed.query
                        and not parsed.fragment
                        and suites == ["stable"]
                        and len(keyring.split()) == 1
                        and keyring.startswith("/")
                    ):
                        candidates.append((uri.rstrip("/"), keyring, source_file))
        else:
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped.startswith("deb "):
                    continue
                match = re.search(r"\[([^]]+)\]\s+(https://\S+)\s+(\S+)", stripped)
                if match:
                    options, uri, suite = match.groups()
                    key = re.search(r"(?:^|\s)signed-by=(\S+)", options)
                    options = match.group(1).lower()
                    if "trusted=yes" in options or "allow-insecure=yes" in options or "check-valid-until=no" in options:
                        raise UpdateFailure("metadata_untrusted")
                    parsed = urlsplit(uri)
                    if suite == "stable" and key and parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment:
                        candidates.append((uri.rstrip("/"), key.group(1), source_file))
    unique = {(uri, keyring, source_file) for uri, keyring, source_file in candidates}
    if len(unique) != 1:
        raise UpdateFailure("prerequisite_missing: apt_source")
    uri, keyring, source_file = next(iter(unique))
    try:
        source_stat = source_file.lstat()
    except OSError as exc:
        raise UpdateFailure("prerequisite_missing: apt_source") from exc
    if source_file.is_symlink() or source_stat.st_uid != 0 or source_stat.st_mode & 0o022:
        raise UpdateFailure("prerequisite_missing: apt_source")
    key_path = Path(keyring)
    try:
        key_stat = key_path.lstat()
    except OSError as exc:
        raise UpdateFailure("prerequisite_missing: apt_keyring") from exc
    if (
        key_path.parent != APT_KEYRING_DIR
        or key_path.is_symlink()
        or not key_path.is_file()
        or key_stat.st_uid != 0
        or key_stat.st_mode & 0o022
        or not os.access(key_path, os.R_OK)
    ):
        raise UpdateFailure("prerequisite_missing: apt_keyring")
    _verify_apt_security_config()
    return uri, keyring


def _verify_apt_security_config() -> None:
    result = subprocess.run(
        ["/usr/bin/apt-config", "dump"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    )
    lowered = result.stdout.lower()
    forbidden = (
        'acquire::check-valid-until "false"',
        'acquire::allowinsecureRepositories "true"'.lower(),
        'acquire::allowdowngradetoinsecureRepositories "true"'.lower(),
    )
    if any(option in lowered for option in forbidden):
        raise UpdateFailure("metadata_untrusted")


def _verify_apt_metadata_dates(source_uri: str) -> None:
    now = datetime.now(timezone.utc)
    parsed = urlsplit(source_uri)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UpdateFailure("metadata_untrusted")
    authority = parsed.netloc.lower()
    repository_path = parsed.path.strip("/").replace("/", "_")
    path_prefix = f"{repository_path}_" if repository_path else ""
    expected_names = {
        f"{authority}_{path_prefix}dists_stable_inrelease",
        f"{authority.replace(':', '%3a')}_{path_prefix}dists_stable_inrelease",
        f"{authority.replace(':', '%3A')}_{path_prefix}dists_stable_inrelease",
    }
    expected_names = {name.lower() for name in expected_names}
    for path in APT_LIST_DIR.glob("*_InRelease"):
        if path.name.lower() not in expected_names:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError):
            continue
        fields = {}
        for line in text.splitlines():
            key, separator, value = line.partition(":")
            if separator and key in {"Origin", "Suite", "Date", "Valid-Until"}:
                fields[key] = value.strip()
        if fields.get("Origin") != "Dmitri" or fields.get("Suite") != "stable":
            continue
        try:
            issued = datetime.strptime(fields["Date"], "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            expiry = datetime.strptime(fields["Valid-Until"], "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError) as exc:
            raise UpdateFailure("metadata_expired") from exc
        if issued > now or expiry <= now:
            raise UpdateFailure("metadata_expired")
        return
    raise UpdateFailure("metadata_unavailable")


def _apt_record_matches(record: str, version: str, digest: str) -> bool:
    fields: dict[str, str] = {}
    for line in record.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return (
        fields.get("Package") == "hardware-agent"
        and fields.get("Version") == version
        and fields.get("Architecture") == "arm64"
        and fields.get("SHA256") == digest
        and bool(fields.get("Filename"))
        and not fields["Filename"].startswith("/")
        and ".." not in Path(fields["Filename"]).parts
    )


def _is_expired_claim_response(exc: BaseException) -> bool:
    """Only the documented backend 410/request_expired closes an unclaimed intent."""
    if getattr(exc, "code", None) != 410:
        return False
    try:
        body = json.loads(exc.read())
    except (AttributeError, OSError, TypeError, ValueError):
        return False
    error = body.get("error") if isinstance(body, dict) else None
    return isinstance(error, dict) and error.get("code") == "request_expired"


def _write_cache_digest(package: Path, version: str) -> None:
    PACKAGE_CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = PACKAGE_CACHE / f"{version}.sha256"
    temporary = manifest.with_name(f".{manifest.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="ascii") as stream:
        stream.write(_sha256(package) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, manifest)
    if os.name == "posix":
        directory = os.open(manifest.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _cache_versioned_package(package: Path, version: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", version):
        raise UpdateFailure("artifact_mismatch")
    PACKAGE_CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    final = PACKAGE_CACHE / f"{version}.deb"
    temporary = PACKAGE_CACHE / f".{version}.{uuid.uuid4().hex}.tmp"
    shutil.copyfile(package, temporary)
    os.chmod(temporary, 0o600)
    _fsync_file(temporary)
    os.replace(temporary, final)
    _fsync_directory(PACKAGE_CACHE)
    _write_cache_digest(package, version)


def _preflight(package: Path, prior: str, target: str) -> None:
    _check_package_manager_idle()
    status = subprocess.run(
        ["/usr/bin/dpkg", "--audit"],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if status.stdout.strip():
        raise UpdateFailure("dpkg_unhealthy")
    architecture = subprocess.run(
        ["/usr/bin/dpkg", "--print-architecture"], check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if architecture != "arm64":
        raise UpdateFailure("unsupported_platform")
    try:
        memory = next(
            int(line.split()[1]) * 1024
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
            if line.startswith("MemAvailable:")
        )
    except (OSError, StopIteration, ValueError) as exc:
        raise UpdateFailure("insufficient_resources") from exc
    if memory < 256 * 1024 * 1024:
        raise UpdateFailure("insufficient_resources")
    usage = shutil.disk_usage(STATE_DIR)
    stats = os.statvfs(STATE_DIR)
    if AGENT_ROOT.exists() and AGENT_ROOT.stat().st_dev != STATE_DIR.stat().st_dev:
        raise UpdateFailure("snapshot_filesystem_mismatch")
    snapshot_bytes, snapshot_inodes = _tree_size(AGENT_ROOT)
    journal_bytes = (STATE_DIR / "state.sqlite3").stat().st_size if (STATE_DIR / "state.sqlite3").exists() else 0
    needed_bytes = snapshot_bytes + (package.stat().st_size * 2) + journal_bytes + 64 * 1024 * 1024
    needed_inodes = snapshot_inodes + 128
    if usage.free < needed_bytes or stats.f_favail < needed_inodes:
        raise UpdateFailure("insufficient_resources")
    catalog = subprocess.run(
        ["/usr/bin/apt-cache", "madison", "hardware-agent"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    )
    if not any(
        len(columns := line.split("|")) >= 2 and columns[1].strip() == target
        for line in catalog.stdout.splitlines()
    ):
        raise UpdateFailure("metadata_untrusted")
    result = subprocess.run(
        [
            "/usr/bin/apt-get",
            "--simulate",
            "--no-download",
            "install",
            f"hardware-agent={target}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
            "DEBIAN_FRONTEND": "noninteractive",
            "LANG": "C.UTF-8",
        },
    )
    for line in result.stdout.splitlines():
        fields = line.split()
        if (
            fields
            and fields[0] == "Inst"
            and (len(fields) < 2 or fields[1] != "hardware-agent")
        ):
            raise UpdateFailure("package_plan_changes_other_packages")
        if (
            fields
            and fields[0] in {"Remv", "Conf"}
            and (
                fields[0] == "Remv" or len(fields) < 2 or fields[1] != "hardware-agent"
            )
        ):
            raise UpdateFailure("package_plan_unsafe")
    if f"{target}" not in result.stdout or prior == target:
        raise UpdateFailure("package_plan_invalid")


def _tree_size(root: Path) -> tuple[int, int]:
    total = 0
    inodes = 0
    if not root.exists():
        return total, inodes
    for path in root.rglob("*"):
        inodes += 1
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError as exc:
            raise UpdateFailure("insufficient_resources") from exc
    return total, inodes


def _check_package_manager_idle() -> None:
    if os.name != "posix":
        raise UpdateFailure("package_manager_busy")
    import fcntl

    for lock_path in ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock"):
        try:
            descriptor = os.open(lock_path, os.O_RDWR)
        except FileNotFoundError:
            continue
        try:
            try:
                fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise UpdateFailure("package_manager_busy") from exc
            finally:
                try:
                    fcntl.lockf(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(descriptor)


def _systemctl(action: str, unit: str) -> None:
    if action not in {"stop", "start", "restart"} or unit != "dmitri-agent.service":
        raise ValueError("unsupported systemd operation")
    subprocess.run(
        ["/usr/bin/systemctl", action, unit],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    )


def _read_env(path: Path) -> dict[str, str]:
    """Read a small KEY=value allowlist without shell evaluation or interpolation."""
    allowed = {"BACKEND_URL", "DEVICE_ID", "DEVICE_PRIVATE_KEY"}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if (
            not separator
            or key not in allowed
            or key in values
            or not value
            or any(c in value for c in "\r\n\0")
        ):
            raise ValueError("invalid agent environment")
        values[key] = value
    if set(values) != allowed or len(values["DEVICE_PRIVATE_KEY"]) != 64:
        raise ValueError("incomplete agent environment")
    from urllib.parse import urlsplit

    endpoint = urlsplit(values["BACKEND_URL"])
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.path not in {"", "/"}
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("invalid backend URL")
    uuid.UUID(values["DEVICE_ID"])
    if any(
        character not in "0123456789abcdefABCDEF"
        for character in values["DEVICE_PRIVATE_KEY"]
    ):
        raise ValueError("invalid device key")
    return values


def _failure_code(error: Exception) -> str:
    message = str(error).lower()
    if "artifact" in message or "package_identity" in message:
        return "artifact_mismatch"
    if "authorization_expired" in message:
        return "authorization_expired"
    if "authorization" in message or "expired" in message:
        return "request_expired"
    if "metadata_expired" in message:
        return "metadata_expired"
    if "metadata" in message or "origin" in message or "suite" in message:
        return "metadata_untrusted"
    if "prerequisite" in message or "updater" in message:
        return "prerequisite_missing"
    if "unsupported_platform" in message or "architecture" in message:
        return "unsupported_platform"
    if "resource" in message or "space" in message or "inode" in message:
        return "insufficient_resources"
    if "dpkg" in message or "package_plan" in message or "apt" in message:
        return "package_manager_busy"
    if "health" in message:
        return "local_health_failed"
    return "install_failed"


def _claim_receipt_matches(
    claim: dict[str, Any],
    digest: str,
    target: str,
    *,
    update_id: str | None = None,
    session_id: str | None = None,
    release_id: str | None = None,
) -> bool:
    required = claim.get("required_updater_version")
    return (
        claim.get("sha256") == digest
        and claim.get("target_package_version") == target
        and (update_id is None or claim.get("update_id") == update_id)
        and (session_id is None or claim.get("session_id") == session_id)
        and (release_id is None or claim.get("release_id") == release_id)
        and type(required) is int
        and 1 <= required <= UPDATER_COMPAT_LEVEL
    )


def _application_version_for_package(package_version: str) -> str:
    """Map the immutable Debian release contract to its upstream app version."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)-1", package_version)
    if not match:
        raise UpdateFailure("artifact_mismatch")
    return match.group(1)


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"--check", "--inspect"}:
        result = request("check" if sys.argv[1] == "--check" else "inspect")
        print(json.dumps(result, separators=(",", ":")))
        return 0 if result.get("ok") else 1
    if len(sys.argv) != 1:
        return 2
    updater = Updater()
    signal.signal(signal.SIGTERM, updater.stop)
    signal.signal(signal.SIGINT, updater.stop)
    updater.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
