#!/usr/bin/python3

from __future__ import annotations

import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

STATE_DIR = Path("/var/lib/dmitri/updates")
RUNTIME_DIR = Path("/run/dmitri-agent-updater")
GATE_PATH = Path("/var/lib/dmitri/update-gate.json")
SOCKET_PATH = RUNTIME_DIR / "control.sock"
MAX_MESSAGE_BYTES = 4096
CHECK_TIMEOUT_SECONDS = 600
CLIENT_TIMEOUT_SECONDS = CHECK_TIMEOUT_SECONDS + 30
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
    ) -> None:
        self.state_dir = state_dir
        self.runtime_dir = runtime_dir
        self.journal_path = state_dir / "state.sqlite3"
        self.gate_path = gate_path
        self.socket_path = runtime_dir / "control.sock"
        self.mutex_path = runtime_dir / "transaction.lock"
        self.stopping = threading.Event()
        self.server_socket: socket.socket | None = None
        self.child_lock = threading.Lock()
        self.children: set[subprocess.Popen[bytes]] = set()

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
                    connection.execute("PRAGMA user_version = 1")
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
                    if not isinstance(request, dict) or set(request) != {"command"}:
                        raise ValueError
                    command = request["command"]
                    if command == "inspect":
                        response = self.inspect()
                    elif command == "check":
                        response = self.check()
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
    def _is_root_peer(connection: socket.socket) -> bool:
        if not hasattr(socket, "SO_PEERCRED"):
            return False
        credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        uid = int.from_bytes(credentials[4:8], byteorder=sys.byteorder, signed=True)
        return uid == 0

    def inspect(self) -> dict[str, Any]:
        try:
            active = self._active_operations()
        except StateCorrupt:
            self._write_gate("state_corrupt", [])
            raise
        return {
            "ok": True,
            "capabilities": ["inspect", "check"],
            "blocked": bool(active) or self.gate_path.exists(),
        }

    def check(self) -> dict[str, Any]:
        if self.stopping.is_set():
            return {"ok": False, "error": "supervisor_stopping"}
        try:
            if self._active_operations() or self.gate_path.exists():
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

    def _run_metadata_refresh(self) -> bool:
        with self.child_lock:
            if self.stopping.is_set():
                return False
            process = subprocess.Popen(
                ["/usr/bin/apt-get", "update"],
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
