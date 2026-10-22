from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "packaging/updater.py"
SPEC = importlib.util.spec_from_file_location("dmitri_updater", MODULE_PATH)
updater_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(updater_module)
Updater = updater_module.Updater
_read_env = updater_module._read_env


def test_verify_package_parses_real_dpkg_deb_field_output(tmp_path, monkeypatch):
    package = tmp_path / "agent.deb"

    class Result:
        stdout = "Package: hardware-agent\nVersion: 1.2.3-1\nArchitecture: arm64\n"

    monkeypatch.setattr(updater_module.subprocess, "run", lambda *a, **k: Result())
    updater_module._verify_package(package, "1.2.3-1")


@pytest.mark.parametrize(
    ("required", "expected"),
    [(1, True), (2, False), (True, False), (None, False)],
)
def test_claim_receipt_enforces_runtime_compatibility_level(required, expected):
    claim = {
        "sha256": "a" * 64,
        "target_package_version": "1.2.3-1",
        "required_updater_version": required,
    }

    assert updater_module._claim_receipt_matches(claim, "a" * 64, "1.2.3-1") is expected


@pytest.fixture
def updater(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Updater:
    scan_lock = tmp_path / "scan.lock"
    scan_lock.touch()
    scan_lock_contract = tmp_path / "scan-lock-path"
    scan_lock_contract.write_text(str(scan_lock), encoding="ascii")
    monkeypatch.setattr(updater_module, "SCAN_LOCK_PATH", scan_lock)
    monkeypatch.setattr(updater_module, "SCAN_LOCK_PATH_FILE", scan_lock_contract)
    instance = Updater(tmp_path / "state", tmp_path / "run", tmp_path / "gate.json")
    instance.initialize()
    return instance


def test_restart_restores_gate_for_pending_operation(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    database = sqlite3.connect(state / "state.sqlite3")
    database.execute(
        "CREATE TABLE operations (operation_id TEXT PRIMARY KEY, phase TEXT NOT NULL)"
    )
    database.execute("INSERT INTO operations VALUES ('op-1', 'installing')")
    database.commit()
    database.close()
    instance = Updater(state, tmp_path / "run", tmp_path / "gate.json")

    instance.initialize()

    assert json.loads((tmp_path / "gate.json").read_text()) == {
        "blocked": True,
        "operation_ids": ["op-1"],
        "reason": "operation_pending",
    }


def test_pending_scan_checkpoint_blocks_update_check_without_live_flock(
    tmp_path: Path,
):
    checkpoint = tmp_path / "scan-finalization.json"
    checkpoint.write_text('{"protocol":1}', encoding="utf-8")
    instance = Updater(
        tmp_path / "state",
        tmp_path / "run",
        tmp_path / "gate.json",
        scan_checkpoint_path=checkpoint,
    )
    instance.initialize()

    assert instance.check() == {"ok": False, "error": "device_busy"}
    assert instance.inspect()["blocked"] is True
    assert instance.inspect()["scan_checkpoint_pending"] is True


def test_corrupt_journal_blocks_mutation_and_preserves_evidence(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    journal = state / "state.sqlite3"
    journal.write_bytes(b"evidence: invalid sqlite")
    instance = Updater(state, tmp_path / "run", tmp_path / "gate.json")

    instance.initialize()

    assert journal.read_bytes() == b"evidence: invalid sqlite"
    assert json.loads((tmp_path / "gate.json").read_text())["reason"] == "state_corrupt"
    assert instance.check() == {"ok": False, "error": "state_corrupt"}


@pytest.mark.parametrize("journal_state", ["active", "corrupt"])
def test_corrupt_gate_is_preserved_before_journal_recovery(
    tmp_path: Path, journal_state: str
):
    state = tmp_path / "state"
    state.mkdir()
    journal = state / "state.sqlite3"
    if journal_state == "corrupt":
        journal.write_bytes(b"evidence: invalid sqlite")
    else:
        database = sqlite3.connect(journal)
        database.execute(
            "CREATE TABLE operations ("
            "operation_id TEXT PRIMARY KEY, phase TEXT NOT NULL)"
        )
        database.execute("INSERT INTO operations VALUES ('op-4', 'installing')")
        database.commit()
        database.close()
    gate = tmp_path / "gate.json"
    gate.write_bytes(b"evidence: invalid gate")
    instance = Updater(state, tmp_path / "run", gate)

    instance.initialize()

    evidence = list(tmp_path.glob("gate.json.corrupt.*"))
    assert len(evidence) == 1
    assert evidence[0].read_bytes() == b"evidence: invalid gate"
    restored = json.loads(gate.read_text())
    if journal_state == "corrupt":
        assert restored["reason"] == "state_corrupt"
        assert journal.read_bytes() == b"evidence: invalid sqlite"
    else:
        assert restored["reason"] == "operation_pending"
        assert restored["operation_ids"] == ["op-4"]


def test_existing_gate_is_not_cleared_without_recovery(updater: Updater):
    updater.gate_path.write_text(
        '{"blocked":true,"reason":"operation_pending","operation_ids":["op-2"]}'
    )

    updater._restore_gate()

    gate = json.loads(updater.gate_path.read_text())
    assert gate["blocked"] is True
    assert gate["reason"] == "recovery_required"
    assert gate["operation_ids"] == ["op-2"]


def test_restart_preserves_claim_pending_gate_for_matching_reporter_retry(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('pending-gate', 'requested')")
        database.execute(
            "INSERT INTO update_details("
            "operation_id,session_id,release_id,target_version,"
            "sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "pending-gate",
                "session",
                "release",
                "1.2.3-1",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "claim_pending",
            ),
        )
    updater._write_gate("operation_pending", ["pending-gate"])
    updater._restore_gate()
    attempts = []

    def offline(path, _body):
        attempts.append(path)
        raise OSError("offline")

    monkeypatch.setattr(updater, "_post_json", offline)

    assert updater._reconcile_pending_claims() is False
    assert attempts == ["/api/v1/agent-updates/pending-gate/claim"]
    assert json.loads(updater.gate_path.read_text())["reason"] == "operation_pending"


def test_claim_pending_expiry_is_decided_only_by_backend_410(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    from io import BytesIO
    from urllib.error import HTTPError

    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('expired-claim', 'requested')")
        database.execute(
            "INSERT INTO update_details("
            "operation_id,session_id,release_id,target_version,"
            "sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "expired-claim",
                "session",
                "release",
                "1.2.3-1",
                "a" * 64,
                "2000-01-01T00:00:00+00:00",
                "claim_pending",
            ),
        )
    attempts = []

    def post(path, _body):
        attempts.append(path)
        raise HTTPError(
            "https://backend.invalid/claim",
            410,
            "gone",
            {},
            BytesIO(b'{"error":{"code":"request_expired"}}'),
        )

    monkeypatch.setattr(updater, "_post_json", post)
    assert updater._reconcile_pending_claims() is True
    assert attempts == ["/api/v1/agent-updates/expired-claim/claim"]
    with sqlite3.connect(updater.journal_path) as database:
        assert database.execute(
            "SELECT phase FROM operations WHERE operation_id='expired-claim'"
        ).fetchone() == ("expired",)


def test_claim_pending_409_is_retried_without_local_expiry(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    from io import BytesIO
    from urllib.error import HTTPError

    with sqlite3.connect(updater.journal_path) as database:
        database.execute(
            "INSERT INTO operations VALUES ('claim-conflict', 'requested')"
        )
        database.execute(
            "INSERT INTO update_details("
            "operation_id,session_id,release_id,target_version,"
            "sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "claim-conflict",
                "session",
                "release",
                "1.2.3-1",
                "a" * 64,
                "2000-01-01T00:00:00+00:00",
                "claim_pending",
            ),
        )
    monkeypatch.setattr(
        updater,
        "_post_json",
        lambda *_args: (_ for _ in ()).throw(
            HTTPError(
                "https://backend.invalid/claim", 409, "conflict", {}, BytesIO(b"{}")
            )
        ),
    )

    assert updater._reconcile_pending_claims() is False
    with sqlite3.connect(updater.journal_path) as database:
        assert database.execute(
            "SELECT phase FROM operations WHERE operation_id='claim-conflict'"
        ).fetchone() == ("requested",)


def test_malformed_gate_is_preserved_as_evidence(updater: Updater):
    updater.gate_path.write_text("not-json")

    updater._restore_gate()

    evidence = list(
        updater.gate_path.parent.glob(f"{updater.gate_path.name}.corrupt.*")
    )
    assert len(evidence) == 1
    assert evidence[0].read_text() == "not-json"
    assert json.loads(updater.gate_path.read_text())["reason"] == "state_corrupt"


def test_check_never_runs_while_an_operation_is_active(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-3', 'preparing')")
    called = False

    def refresh() -> bool:
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(updater, "_run_metadata_refresh", refresh)
    updater._restore_gate()

    assert updater.check() == {"ok": False, "error": "device_busy"}
    assert called is False


@pytest.mark.skipif(os.name != "posix", reason="POSIX flock required")
def test_check_serializes_with_another_metadata_transaction(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    started = threading.Event()
    finish = threading.Event()

    def refresh() -> bool:
        started.set()
        finish.wait(timeout=5)
        return True

    monkeypatch.setattr(updater, "_run_metadata_refresh", refresh)
    first_result: list[dict[str, object]] = []
    first = threading.Thread(target=lambda: first_result.append(updater.check()))
    first.start()
    assert started.wait(timeout=2)
    try:
        assert updater.check() == {"ok": False, "error": "device_busy"}
    finally:
        finish.set()
        first.join(timeout=2)
    assert first_result == [{"ok": True, "metadata_refreshed": True}]


def test_metadata_refresh_uses_only_fixed_apt_update(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    calls: list[tuple[list[str], dict[str, str]]] = []

    class Process:
        pid = 42

        def wait(self, timeout: int) -> int:
            assert timeout == updater_module.CHECK_TIMEOUT_SECONDS
            return 0

    def popen(command: list[str], **kwargs: object) -> Process:
        calls.append((command, kwargs["env"]))
        return Process()

    monkeypatch.setattr(updater_module.subprocess, "Popen", popen)

    assert updater._run_metadata_refresh() is True
    assert calls == [
        (
            ["/usr/bin/apt-get", "-o", "APT::Update::Error-Mode=any", "update"],
            {
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "DEBIAN_FRONTEND": "noninteractive",
                "LANG": "C.UTF-8",
            },
        )
    ]


@pytest.mark.skipif(os.name != "posix", reason="POSIX Unix socket credentials required")
def test_malformed_and_unauthorized_socket_messages_are_rejected(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: False)
    client.sendall(b'{"command":"check"}\n')
    client.shutdown(socket.SHUT_WR)
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.settimeout(0.2)
    try:
        response = client.recv(100)
    except ConnectionResetError:
        response = b""
    assert response == b""
    client.close()
    worker.join(timeout=1)

    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(b'{"command":"check","argv":["arbitrary"]}\n')
    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)
    assert response == {"ok": False, "error": "invalid_request"}

    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(b'{"command":"inspect"}\n{"command":"check"}')
    client.shutdown(socket.SHUT_WR)
    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)
    assert response == {"ok": False, "error": "invalid_request"}


def test_readiness_handshake_binds_nonce_mainpid_invocation_and_package(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    monkeypatch.setattr(updater, "_peer_credentials", lambda _: (0, 412))
    monkeypatch.setattr(updater, "readiness_identity", lambda: (412, "invocation-1"))
    monkeypatch.setattr(updater, "package_version", lambda: "1.0.7-1")
    monkeypatch.setattr(updater, "app_version", lambda: "1.0.7")
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(
        json.dumps(
            {
                "command": "readiness",
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )
    challenge = json.loads(client.recv(1024))
    client.sendall(
        json.dumps(
            {
                **challenge,
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )
    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)

    assert response["ok"] is True
    assert response["main_pid"] == 412
    assert response["invocation_id"] == "invocation-1"
    assert len(response["nonce"]) == 48


def test_boot_recovery_reuses_matching_handshake_from_already_ready_agent(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    updater.last_readiness = (412, "boot-invocation", "1.2.3", "1.2.3-1")
    calls = []
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.3-1")
    monkeypatch.setattr(updater, "app_version", lambda: "1.2.3")
    monkeypatch.setattr(updater, "readiness_identity", lambda: (412, "boot-invocation"))
    monkeypatch.setattr(
        updater,
        "_run_checked",
        lambda argv, **_kwargs: (
            "install ok installed"
            if "dpkg-query" in argv[0]
            else '{"ok":true,"version":"1.2.3"}'
        ),
    )
    monkeypatch.setattr(updater_module, "_systemctl", lambda *args: calls.append(args))
    monkeypatch.setattr(updater_module.time, "sleep", lambda _seconds: None)

    assert updater._verify_local_health("1.2.3-1") == "boot-invocation"
    assert calls == [("start", "dmitri-agent.service")]
    assert updater.last_readiness == (412, "boot-invocation", "1.2.3", "1.2.3-1")


def test_app_version_uses_installed_agent_runtime(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "1.0.7\n", "")

    monkeypatch.setattr(updater_module.subprocess, "run", run)

    assert Updater._installed_agent_app_version() == "1.0.7"
    assert calls[0][0] == [
        "/opt/dmitri-agent/.venv/bin/python",
        "-c",
        "from agent.version import installed_version; print(installed_version())",
    ]
    assert calls[0][1]["check"] is True
    assert calls[0][1]["timeout"] == 5


def test_app_version_fails_closed_when_installed_runtime_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, "python")

    monkeypatch.setattr(updater_module.subprocess, "run", run)

    with pytest.raises(subprocess.CalledProcessError):
        Updater._installed_agent_app_version()


def test_readiness_rejects_stale_process_invocation(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    monkeypatch.setattr(updater, "_peer_credentials", lambda _: (0, 412))
    identities = iter([(412, "invocation-1"), (412, "invocation-2")])
    monkeypatch.setattr(updater, "readiness_identity", lambda: next(identities))
    monkeypatch.setattr(updater, "package_version", lambda: "1.0.7-1")
    monkeypatch.setattr(updater, "app_version", lambda: "1.0.7")
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(
        json.dumps(
            {
                "command": "readiness",
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )
    challenge = json.loads(client.recv(1024))
    client.sendall(
        json.dumps(
            {
                **challenge,
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )
    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)

    assert response == {"ok": False, "error": "stale_session"}


def test_readiness_rejects_application_version_that_does_not_match_installed_identity(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    monkeypatch.setattr(updater, "_peer_credentials", lambda _: (0, 412))
    monkeypatch.setattr(updater, "readiness_identity", lambda: (412, "invocation-1"))
    monkeypatch.setattr(updater, "package_version", lambda: "1.0.7-1")
    monkeypatch.setattr(updater, "app_version", lambda: "1.0.8")
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(
        json.dumps(
            {
                "command": "readiness",
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )
    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)

    assert response == {"ok": False, "error": "stale_session"}


def test_readiness_rejects_peer_pid_that_is_not_mainpid(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    monkeypatch.setattr(updater, "_peer_credentials", lambda _: (0, 411))
    monkeypatch.setattr(updater, "readiness_identity", lambda: (412, "invocation-1"))
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(
        json.dumps(
            {
                "command": "readiness",
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )

    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)

    assert response == {"ok": False, "error": "stale_session"}


def test_readiness_rejects_wrong_nonce(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    monkeypatch.setattr(updater, "_peer_credentials", lambda _: (0, 412))
    monkeypatch.setattr(updater, "readiness_identity", lambda: (412, "invocation-1"))
    monkeypatch.setattr(updater, "package_version", lambda: "1.0.7-1")
    monkeypatch.setattr(updater, "app_version", lambda: "1.0.7")
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    client.sendall(
        json.dumps(
            {
                "command": "readiness",
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )
    challenge = json.loads(client.recv(1024))
    client.sendall(
        json.dumps(
            {
                **challenge,
                "nonce": "0" * 48,
                "app_version": "1.0.7",
                "package_version": "1.0.7-1",
            }
        ).encode()
        + b"\n"
    )

    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)

    assert response == {"ok": False, "error": "stale_session"}


def test_inspect_reports_update_context_and_suppresses_ready_without_trust(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    def missing_trust():
        raise updater_module.UpdateFailure("apt_keyring")

    monkeypatch.setattr(updater_module, "_verify_dedicated_apt_source", missing_trust)
    with updater._connect() as db, db:
        db.execute("INSERT INTO operations VALUES ('op-1', 'installing')")
        db.execute(
            "INSERT INTO update_details("
            "operation_id,session_id,release_id,target_version,sha256,deadline,"
            "phase,invocation_id) "
            "VALUES('op-1','session-1','release-1','1.2.3-1',?,"
            "'2099-01-01T00:00:00+00:00','installing','invocation-1')",
            ("a" * 64,),
        )

    result = updater.inspect()

    assert result["agent_update_ready"] is False
    assert result["updater_version"] == 1
    assert result["update_context"] == {
        "operation_id": "op-1",
        "phase": "installing",
        "invocation_id": "invocation-1",
        "target_package_version": "1.2.3-1",
    }


def test_inspect_requires_authenticated_cached_installed_recovery_baseline(
    updater: Updater, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    cache = tmp_path / "cache"
    cache.mkdir()
    package_version = "1.2.3-1"
    package = cache / f"{package_version}.deb"
    package.write_bytes(b"recovery baseline")
    digest = updater_module._sha256(package)
    (cache / f"{package_version}.sha256").write_text(digest + "\n", encoding="ascii")
    updater.package_version = lambda: package_version
    monkeypatch.setattr(updater_module, "PACKAGE_CACHE", cache)
    monkeypatch.setattr(updater_module.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri-agent.gpg"),
    )
    monkeypatch.setattr(updater_module, "_verify_package", lambda *_args: None)
    authenticated = []
    monkeypatch.setattr(
        updater_module,
        "_verify_apt_origin_suite",
        lambda version, package_digest: authenticated.append((version, package_digest)),
    )
    monkeypatch.setattr(
        updater_module,
        "_read_env",
        lambda _path: {
            "BACKEND_URL": "https://api.example.test",
            "DEVICE_ID": "10000000-0000-0000-0000-000000000001",
            "DEVICE_PRIVATE_KEY": "a" * 64,
        },
    )

    result = updater.inspect()

    assert result["agent_update_ready"] is True
    assert result["os_suite"] == "stable"
    assert authenticated == [(package_version, digest)]

    env_file = tmp_path / "agent.env"
    monkeypatch.setattr(updater_module, "AGENT_ENV", env_file)
    monkeypatch.setattr(updater_module, "_read_env", _read_env)
    result = updater.inspect()
    assert result["agent_update_ready"] is False

    env_file.write_text(
        "BACKEND_URL=http://192.168.15.153:8000\n"
        "DEVICE_ID=10000000-0000-0000-0000-000000000001\n"
        f"DEVICE_PRIVATE_KEY={'a' * 64}\n",
        encoding="utf-8",
    )
    result = updater.inspect()
    assert result["agent_update_ready"] is False

    (cache / f"{package_version}.sha256").write_text("0" * 64 + "\n", encoding="ascii")
    result = updater.inspect()
    assert result["agent_update_ready"] is False


def test_update_journal_duplicate_is_idempotent_and_old_session_is_rejected(
    updater: Updater,
):
    with updater._connect() as db, db:
        db.execute("INSERT INTO operations VALUES ('op-1', 'installing')")
        db.execute(
            "INSERT INTO update_details("
            "operation_id,session_id,release_id,target_version,sha256,deadline,phase) "
            "VALUES('op-1','session-1','release-1','1.2.3-1',?,'2099-01-01T00:00:00+00:00','installing')",
            ("a" * 64,),
        )

    deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1)
    same = updater._apply_claimed_update(
        "op-1", "session-1", "release-1", "1.2.3-1", "a" * 64, deadline
    )
    stale = updater._apply_claimed_update(
        "op-1", "session-2", "release-1", "1.2.3-1", "a" * 64, deadline
    )

    assert same == {"ok": True, "phase": "installing", "replayed": True}
    assert stale == {"ok": False, "error": "stale_session"}


def _handle_socket_payload(
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> bytes:
    client, server = socket.socketpair()
    monkeypatch.setattr(updater, "_is_root_peer", lambda _: True)
    with client:
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        updater._handle_connection(server)
        return client.recv(1024)


@pytest.mark.parametrize(
    "payload",
    [b"\xff\n", b"\xff"],
    ids=["invalid-utf8-line", "invalid-utf8-without-newline"],
)
def test_socket_rejects_invalid_utf8(
    updater: Updater, monkeypatch: pytest.MonkeyPatch, payload: bytes
):
    response = _handle_socket_payload(updater, monkeypatch, payload)

    assert json.loads(response) == {"ok": False, "error": "invalid_request"}


def test_socket_rejects_oversized_message(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    response = _handle_socket_payload(
        updater,
        monkeypatch,
        b"x" * (updater_module.MAX_MESSAGE_BYTES + 1),
    )

    assert json.loads(response) == {"ok": False, "error": "invalid_request"}


@pytest.mark.skipif(
    os.name != "posix" or not hasattr(os, "killpg"),
    reason="POSIX process groups required",
)
def test_supervisor_teardown_terminates_owned_process_group(updater: Updater):
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    updater.children.add(child)

    updater._stop_children()

    assert child.poll() is not None
    assert child.returncode != 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits required")
def test_journal_and_runtime_permissions_are_restricted(updater: Updater):
    assert updater.state_dir.stat().st_mode & 0o777 == 0o700
    assert updater.runtime_dir.stat().st_mode & 0o777 == 0o700
    assert updater.journal_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits required")
def test_gate_remains_world_readable_under_restrictive_umask(updater: Updater):
    previous_umask = os.umask(0o077)
    try:
        updater._write_gate("operation_pending", ["op-5"])
    finally:
        os.umask(previous_umask)

    assert updater.gate_path.stat().st_mode & 0o777 == 0o644


def test_update_environment_parser_does_not_evaluate_shell(tmp_path: Path):
    path = tmp_path / "agent.env"
    path.write_text(
        "BACKEND_URL=https://example.test\n"
        "DEVICE_ID=00000000-0000-0000-0000-000000000001\n"
        "DEVICE_PRIVATE_KEY=" + "a" * 64 + "\n",
        encoding="utf-8",
    )

    values = _read_env(path)

    assert values["BACKEND_URL"] == "https://example.test"
    path.write_text(
        "BACKEND_URL=$(touch /tmp/should-not-exist)\n"
        "DEVICE_ID=00000000-0000-0000-0000-000000000001\n"
        "DEVICE_PRIVATE_KEY=" + "a" * 64 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        _read_env(path)


def test_update_event_reporter_retries_oldest_unacked_sequence(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-9', 'installing')")
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,"
            "sha256,deadline,phase,sequence,pending_event,ack_sequence) "
            "VALUES('op-9','session','release','1.2.3','" + "a" * 64 + "',"
            "'2030-01-01T00:00:00+00:00','installing',2,'{}',0)"
        )
        database.execute(
            "INSERT INTO update_events VALUES ('op-9',1,'{\"sequence\":1}')"
        )
        database.execute(
            "INSERT INTO update_events VALUES ('op-9',2,'{\"sequence\":2}')"
        )
    posted: list[dict[str, object]] = []

    def post(_path: str, body: dict[str, object]) -> dict[str, object]:
        posted.append(body)
        return {"ack_sequence": body["sequence"]}

    monkeypatch.setattr(updater, "_post_json", post)

    updater._flush_events("op-9")

    assert [event["sequence"] for event in posted] == [1, 2]
    with sqlite3.connect(updater.journal_path) as database:
        ack_sequence = database.execute(
            "SELECT ack_sequence FROM update_details WHERE operation_id='op-9'"
        ).fetchone()[0]
    assert ack_sequence == 2


def test_lost_event_ack_replays_same_committed_event_after_restart(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    event = {
        "sequence": 1,
        "phase": "awaiting_confirmation",
        "local_outcome": "succeeded",
        "observed_version": "1.2.3",
    }
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-ack-loss', 'verifying')")
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,sha256,deadline,phase,sequence,pending_event,ack_sequence) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "op-ack-loss",
                "session",
                "release",
                "1.2.3",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "awaiting_confirmation",
                1,
                json.dumps(event, separators=(",", ":")),
                0,
            ),
        )
        database.execute(
            "INSERT INTO update_events VALUES (?,?,?)",
            ("op-ack-loss", 1, json.dumps(event, separators=(",", ":"))),
        )

    committed: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []

    def post(_path: str, body: dict[str, object]) -> dict[str, object]:
        attempts.append(body.copy())
        if not committed:
            committed.append(body.copy())
            raise OSError("connection closed after server commit")
        assert body == committed[0]
        return {"ack_sequence": body["sequence"]}

    monkeypatch.setattr(updater, "_post_json", post)
    assert updater._flush_events("op-ack-loss") is False
    with sqlite3.connect(updater.journal_path) as database:
        assert database.execute(
            "SELECT ack_sequence FROM update_details WHERE operation_id='op-ack-loss'"
        ).fetchone() == (0,)

    restarted = Updater(
        updater.state_dir,
        updater.runtime_dir,
        updater.gate_path,
        package_version=lambda: "1.2.3",
    )
    restarted.initialize()
    monkeypatch.setattr(restarted, "_post_json", post)
    assert restarted._flush_events("op-ack-loss") is True

    assert attempts == [event, event]
    assert committed == [event]
    with sqlite3.connect(restarted.journal_path) as database:
        assert database.execute(
            "SELECT ack_sequence,pending_event FROM update_details "
            "WHERE operation_id='op-ack-loss'"
        ).fetchone() == (1, None)
        assert database.execute(
            "SELECT COUNT(*) FROM update_events WHERE operation_id='op-ack-loss'"
        ).fetchone() == (1,)


def test_supervisor_reports_recovery_event_with_broken_agent_tree_after_restart(
    updater: Updater, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    update_id = "op-broken-agent-tree"
    session_id = "session-broken-agent-tree"
    agent_root = tmp_path / "agent-root"
    broken_python = agent_root / ".venv/bin/python"
    broken_python.parent.mkdir(parents=True)
    broken_python.write_text("#!/missing/python\n", encoding="utf-8")
    missing_snapshot = tmp_path / "snapshot-that-was-lost"
    package_cache = tmp_path / "package-cache"
    package_cache.mkdir()
    (package_cache / "1.2.2-1.deb").write_bytes(b"test package")
    monkeypatch.setattr(updater_module, "AGENT_ROOT", agent_root)
    monkeypatch.setattr(updater_module, "PACKAGE_CACHE", package_cache)
    monkeypatch.setattr(updater_module, "_systemctl", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_verify_cache_digest", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_verify_package", lambda *_args: None)
    monkeypatch.setattr(updater, "_run_checked", lambda *_args, **_kwargs: "")
    updater.package_version = lambda: "1.2.3-1"

    with sqlite3.connect(updater.journal_path) as database:
        database.execute(
            "INSERT INTO operations VALUES (?, 'installing')", (update_id,)
        )
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,sha256,deadline,prior_version,snapshot,phase) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                update_id,
                session_id,
                "release",
                "1.2.3-1",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "1.2.2-1",
                str(missing_snapshot),
                "installing",
            ),
        )

    def backend_offline(*_args, **_kwargs):
        raise OSError("backend unavailable")

    monkeypatch.setattr(updater, "_post_json", backend_offline)

    result = updater._recover_update(update_id, session_id, "local_health_failed")

    assert result == {"ok": False, "error": "needs_intervention"}
    assert not agent_root.exists()
    assert json.loads(updater.gate_path.read_text(encoding="utf-8")) == {
        "blocked": True,
        "operation_ids": [update_id],
        "reason": "recovery_required",
    }
    with sqlite3.connect(updater.journal_path) as database:
        events = [
            json.loads(row[0])
            for row in database.execute(
                "SELECT body FROM update_events WHERE operation_id=? ORDER BY sequence",
                (update_id,),
            )
        ]
        persisted = database.execute(
            "SELECT sequence,ack_sequence,pending_event FROM update_details "
            "WHERE operation_id=?",
            (update_id,),
        ).fetchone()
        first_event_json = json.dumps(events[0], separators=(",", ":"), sort_keys=True)
        assert persisted == (2, 0, first_event_json)
    assert [event["phase"] for event in events] == ["recovering", "needs_intervention"]
    assert events[-1]["error_code"] == "recovery_failed"

    restarted = Updater(
        updater.state_dir,
        updater.runtime_dir,
        updater.gate_path,
        package_version=lambda: "1.2.3-1",
    )
    restarted.initialize()
    restarted.report_retry_delay = 0.01
    committed: dict[int, dict[str, object]] = {}

    def backend_recovers(_path: str, body: dict[str, object]) -> dict[str, object]:
        sequence = body["sequence"]
        assert isinstance(sequence, int)
        committed.setdefault(sequence, body.copy())
        assert committed[sequence] == body
        return {"ack_sequence": sequence}

    monkeypatch.setattr(restarted, "_post_json", backend_recovers)
    reporter = threading.Thread(target=restarted._report_pending_events, daemon=True)
    reporter.start()
    try:
        deadline = updater_module.time.monotonic() + 2
        while updater_module.time.monotonic() < deadline:
            with sqlite3.connect(restarted.journal_path) as database:
                ack_sequence = database.execute(
                    "SELECT ack_sequence FROM update_details WHERE operation_id=?",
                    (update_id,),
                ).fetchone()[0]
            if ack_sequence == 2:
                break
            updater_module.time.sleep(0.01)
        assert ack_sequence == 2
    finally:
        restarted.stopping.set()
        reporter.join(timeout=2)

    assert not reporter.is_alive()
    assert [committed[sequence]["phase"] for sequence in sorted(committed)] == [
        "recovering",
        "needs_intervention",
    ]
    with sqlite3.connect(restarted.journal_path) as database:
        assert database.execute(
            "SELECT sequence,ack_sequence,pending_event FROM update_details "
            "WHERE operation_id=?",
            (update_id,),
        ).fetchone() == (2, 2, None)


def test_replayed_update_frame_returns_journaled_phase_without_install(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-replay', 'installing')")
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,"
            "sha256,deadline,phase) VALUES('op-replay','session','release','1.2.3','"
            + "a" * 64
            + "','2030-01-01T00:00:00+00:00','installing')"
        )
    monkeypatch.setattr(
        updater,
        "_run_checked",
        lambda *_args, **_kwargs: pytest.fail("must not install"),
    )

    result = updater._apply_claimed_update(
        "op-replay",
        "session",
        "release",
        "1.2.3",
        "a" * 64,
        updater_module.datetime.now(updater_module.timezone.utc),
    )

    assert result == {"ok": True, "phase": "installing", "replayed": True}


def test_startup_resumes_verified_target_without_reinstall(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-resume', 'verifying')")
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,"
            "sha256,deadline,phase) VALUES('op-resume','session','release','1.2.3','"
            + "a" * 64
            + "','2030-01-01T00:00:00+00:00','verifying')"
        )
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.3")
    monkeypatch.setattr(updater, "app_version", lambda: "1.2.3")
    monkeypatch.setattr(updater, "_verify_local_health", lambda _target: "invocation")
    monkeypatch.setattr(
        updater,
        "_post_json",
        lambda *_args, **_kwargs: {"ack_sequence": 1},
    )
    updater._write_gate("operation_pending", ["op-resume"])

    updater._resume_interrupted_update()

    with sqlite3.connect(updater.journal_path) as database:
        phases = [
            json.loads(row[0])["phase"]
            for row in database.execute(
                "SELECT body FROM update_events "
                "WHERE operation_id='op-resume' ORDER BY sequence"
            )
        ]
    assert phases == ["awaiting_confirmation"]
    assert not updater.gate_path.exists()


@pytest.mark.parametrize("phase", ["installing", "verifying"])
def test_restart_accepts_installed_target_without_replaying_dpkg(
    updater: Updater, monkeypatch: pytest.MonkeyPatch, phase: str
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-boundary', ?)", (phase,))
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "op-boundary",
                "session",
                "release",
                "1.2.3",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                phase,
            ),
        )
    emitted = []
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.3")
    monkeypatch.setattr(updater, "_verify_local_health", lambda _target: "invocation")
    monkeypatch.setattr(updater, "_emit", lambda *args, **kwargs: emitted.append(args))
    monkeypatch.setattr(
        updater,
        "_recover_update",
        lambda *_args: pytest.fail("healthy target must not be reinstalled"),
    )
    updater._write_gate("operation_pending", ["op-boundary"])

    updater._resume_interrupted_update()

    expected = []
    if phase == "installing":
        expected.append(("op-boundary", "session", "verifying", None, None))
    expected.append(
        ("op-boundary", "session", "awaiting_confirmation", "succeeded", "invocation")
    )
    assert emitted == expected
    assert not updater.gate_path.exists()


def test_restart_with_unverified_target_attempts_recovery_once(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-mismatch', 'installing')")
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "op-mismatch",
                "session",
                "release",
                "1.2.3",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "installing",
            ),
        )
    calls = []
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.2")
    monkeypatch.setattr(
        updater,
        "_recover_update",
        lambda *args: calls.append(args) or {"ok": False, "error": "rolled_back"},
    )

    updater._resume_interrupted_update()

    assert calls == [("op-mismatch", "session", "install_failed")]


def test_restart_does_not_repeat_interrupted_recovery(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute(
            "INSERT INTO operations VALUES ('op-recovering', 'recovering')"
        )
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,sha256,deadline,phase,recovery_attempts) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                "op-recovering",
                "session",
                "release",
                "1.2.3",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "recovering",
                1,
            ),
        )
    emitted = []
    monkeypatch.setattr(updater, "_emit", lambda *args, **kwargs: emitted.append(args))
    monkeypatch.setattr(
        updater,
        "_recover_update",
        lambda *_args: pytest.fail("recovery must not loop after restart"),
    )

    updater._resume_interrupted_update()

    assert emitted[0][:5] == (
        "op-recovering",
        "session",
        "needs_intervention",
        "needs_intervention",
        None,
    )
    assert updater.gate_path.exists()


def test_startup_recovery_holds_exclusive_scan_lock(
    updater: Updater, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    if os.name != "posix":
        pytest.skip("Linux flock semantics")
    import fcntl

    lock_path = tmp_path / "scan.lock"
    lock_path.touch()
    lock_contract = tmp_path / "scan-lock-path"
    lock_contract.write_text(str(lock_path), encoding="ascii")
    monkeypatch.setattr(updater_module, "SCAN_LOCK_PATH", lock_path)
    monkeypatch.setattr(updater_module, "SCAN_LOCK_PATH_FILE", lock_contract)
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('op-lock', 'verifying')")
        database.execute(
            "INSERT INTO update_details(operation_id,session_id,release_id,"
            "target_version,"
            "sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "op-lock",
                "session",
                "release",
                "1.2.3",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "verifying",
            ),
        )
    entered = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.3")

    def health(_target: str) -> str:
        entered.set()
        assert release.wait(5)
        return "invocation"

    monkeypatch.setattr(updater, "_verify_local_health", health)
    monkeypatch.setattr(updater, "_emit", lambda *_args, **_kwargs: None)
    worker = threading.Thread(target=updater._resume_interrupted_update)
    worker.start()
    try:
        assert entered.wait(5)
        contender = os.open(lock_path, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(contender)
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()


def test_apt_policy_requires_fixed_origin_and_suite(monkeypatch: pytest.MonkeyPatch):
    class Result:
        stdout = (
            "hardware-agent:\n"
            "  Candidate: 1.2.3-1\n"
            "  Version table:\n"
            "     1.2.3-1 500\n"
            "        500 https://apt.example stable/main arm64 Packages\n"
            "           release o=Dmitri,a=stable,n=stable,l=Dmitri,c=main,b=arm64\n"
        )

    monkeypatch.setattr(
        updater_module.subprocess,
        "run",
        lambda *_args, **_kwargs: Result(),
    )
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri.gpg"),
    )
    monkeypatch.setattr(
        updater_module, "_verify_apt_metadata_dates", lambda *_args: None
    )
    updater_module._verify_apt_origin_suite("1.2.3-1")
    Result.stdout = Result.stdout.replace(
        "https://apt.example", "https://other.example"
    )
    with pytest.raises(updater_module.UpdateFailure, match="metadata_untrusted"):
        updater_module._verify_apt_origin_suite("1.2.3-1")


def test_apt_policy_rejects_target_available_only_from_other_source(
    monkeypatch: pytest.MonkeyPatch,
):
    class Result:
        stdout = (
            "hardware-agent:\n  Candidate: 1.2.3-1\n  Version table:\n"
            "     1.2.3-1 500\n"
            "        500 https://untrusted.example stable/main arm64 Packages\n"
            "           release o=Dmitri,a=stable,n=stable\n"
        )

    monkeypatch.setattr(
        updater_module.subprocess, "run", lambda *_args, **_kwargs: Result()
    )
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri.gpg"),
    )
    monkeypatch.setattr(
        updater_module, "_verify_apt_metadata_dates", lambda *_args: None
    )
    with pytest.raises(updater_module.UpdateFailure, match="metadata_untrusted"):
        updater_module._verify_apt_origin_suite("1.2.3-1")


def test_apt_policy_trusts_installed_version_from_fixed_origin(
    monkeypatch: pytest.MonkeyPatch,
):
    class Result:
        stdout = (
            "hardware-agent:\n  Candidate: 1.2.3-1\n  Version table:\n"
            "     1.2.3-1 500\n"
            "        500 https://apt.example stable/main arm64 Packages\n"
            " *** 1.2.2-1 500\n"
            "        500 https://apt.example stable/main arm64 Packages\n"
            "     100 /var/lib/dpkg/status\n"
        )

    monkeypatch.setattr(
        updater_module.subprocess, "run", lambda *_args, **_kwargs: Result()
    )
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri.gpg"),
    )
    monkeypatch.setattr(
        updater_module, "_verify_apt_metadata_dates", lambda *_args: None
    )
    updater_module._verify_apt_origin_suite("1.2.2-1")


def test_apt_policy_installed_status_row_does_not_inherit_other_version_origin(
    monkeypatch: pytest.MonkeyPatch,
):
    class Result:
        stdout = (
            "hardware-agent:\n  Candidate: 1.2.3-1\n  Version table:\n"
            "     1.2.3-1 500\n"
            "        500 https://apt.example stable/main arm64 Packages\n"
            " *** 1.2.2-1 100\n"
            "     100 /var/lib/dpkg/status\n"
        )

    monkeypatch.setattr(
        updater_module.subprocess, "run", lambda *_args, **_kwargs: Result()
    )
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri.gpg"),
    )
    monkeypatch.setattr(
        updater_module, "_verify_apt_metadata_dates", lambda *_args: None
    )
    with pytest.raises(updater_module.UpdateFailure, match="metadata_untrusted"):
        updater_module._verify_apt_origin_suite("1.2.2-1")


def test_apt_package_hash_must_match_signed_index_record(
    monkeypatch: pytest.MonkeyPatch,
):
    import tempfile

    class Result:
        def __init__(self, stdout: str):
            self.stdout = stdout

    policy = Result(
        "hardware-agent:\n  Candidate: 1.2.3-1\n  Version table:\n"
        "     1.2.3-1 500\n"
        "        500 https://apt.example stable/main arm64 Packages\n"
        "           release o=Dmitri,a=stable,n=stable\n"
    )
    package_record = (
        "Package: hardware-agent\nVersion: 1.2.3-1\n"
        "Architecture: arm64\nFilename: pool/main/h/hardware-agent.deb\nSHA256: "
        + "a" * 64
        + "\n"
    )
    list_dir = Path(tempfile.mkdtemp())
    index_file = list_dir / "apt.example_dists_stable_main_binary-arm64_Packages.lz4"
    index_file.write_bytes(b"signed-index-cache")
    monkeypatch.setattr(updater_module, "APT_LIST_DIR", list_dir)

    def run(args, **_kwargs):
        if args[1] == "policy":
            return policy
        if args[1] == "indextargets":
            return Result(
                "https://apt.example/dists/stable/main/binary-arm64/Packages|"
                f"{index_file}|Packages|stable|main|arm64\n"
                "https://other.example/dists/stable/main/binary-arm64/Packages|"
                f"{index_file}|Packages|stable|main|arm64\n"
            )
        assert args[1:3] == ["cat-file", str(index_file)]
        return Result(package_record)

    monkeypatch.setattr(updater_module.subprocess, "run", run)
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri.gpg"),
    )
    monkeypatch.setattr(
        updater_module, "_verify_apt_metadata_dates", lambda *_args: None
    )
    updater_module._verify_apt_origin_suite("1.2.3-1", "a" * 64)
    with pytest.raises(updater_module.UpdateFailure, match="artifact_mismatch"):
        updater_module._verify_apt_origin_suite("1.2.3-1", "b" * 64)


def test_apt_hash_cannot_be_satisfied_by_competing_source_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    class Result:
        def __init__(self, stdout: str):
            self.stdout = stdout

    policy = Result(
        "hardware-agent:\n  Candidate: 1.2.3-1\n  Version table:\n"
        "     1.2.3-1 500\n"
        "        500 https://apt.example stable/main arm64 Packages\n"
    )
    lists = tmp_path / "lists"
    lists.mkdir()
    other_index = lists / "other_dists_stable_Packages.lz4"
    other_index.write_bytes(b"other")
    dedicated_index = lists / "apt.example_dists_stable_main_binary-arm64_Packages.lz4"
    dedicated_index.write_bytes(b"dedicated")
    monkeypatch.setattr(
        updater_module,
        "APT_LIST_DIR",
        lists,
    )
    monkeypatch.setattr(
        updater_module,
        "_verify_dedicated_apt_source",
        lambda: ("https://apt.example", "/etc/apt/keyrings/dmitri.gpg"),
    )
    monkeypatch.setattr(
        updater_module, "_verify_apt_metadata_dates", lambda *_args: None
    )

    def run(args, **_kwargs):
        if args[1] == "policy":
            return policy
        if args[1] == "indextargets":
            return Result(
                "https://other.example/dists/stable/main/binary-arm64/Packages|"
                f"{other_index}|Packages|stable|main|arm64\n"
                "https://apt.example/dists/stable/main/binary-arm64/Packages|"
                f"{dedicated_index}|Packages|stable|main|arm64\n"
            )
        return Result(
            "Package: hardware-agent\nVersion: 1.2.3-1\nArchitecture: arm64\n"
            "Filename: pool/main/h/target.deb\nSHA256: " + "b" * 64 + "\n"
        )

    monkeypatch.setattr(updater_module.subprocess, "run", run)
    with pytest.raises(updater_module.UpdateFailure, match="artifact_mismatch"):
        updater_module._verify_apt_origin_suite("1.2.3-1", "a" * 64)


def test_apt_source_rejects_trusted_yes_and_requires_dedicated_keyring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source_dir = tmp_path / "sources.list.d"
    source_dir.mkdir()
    keyring_dir = tmp_path / "keyrings"
    keyring_dir.mkdir()
    source_file = source_dir / "dmitri.sources"
    source_file.write_text(
        "Types: deb\nURIs: https://apt.example\nSuites: stable\n"
        f"Signed-By: {keyring_dir / 'dmitri.gpg'}\nTrusted: yes\n",
        encoding="utf-8",
    )
    keyring = keyring_dir / "dmitri.gpg"
    keyring.write_bytes(b"keyring")
    monkeypatch.setattr(updater_module, "APT_SOURCE_LIST", tmp_path / "missing.list")
    monkeypatch.setattr(updater_module, "APT_SOURCE_DIR", source_dir)
    monkeypatch.setattr(updater_module, "APT_KEYRING_DIR", keyring_dir)
    with pytest.raises(updater_module.UpdateFailure, match="metadata_untrusted"):
        updater_module._verify_dedicated_apt_source()
    source_file.write_text(
        "Types: deb\nURIs: https://apt.example\nSuites: stable\n"
        f"Signed-By: {keyring_dir / 'missing.gpg'}\n",
        encoding="utf-8",
    )
    original_lstat = Path.lstat

    def source_is_root_owned(path: Path):
        result = original_lstat(path)
        if path == source_file:
            values = list(result)
            values[4] = 0
            return os.stat_result(values)
        return result

    monkeypatch.setattr(Path, "lstat", source_is_root_owned)
    with pytest.raises(updater_module.UpdateFailure, match="apt_keyring"):
        updater_module._verify_dedicated_apt_source()


def test_metadata_expiry_is_checked_for_the_configured_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import datetime

    lists = tmp_path / "lists"
    lists.mkdir()
    expired = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    date = expired.strftime("%a, %d %b %Y %H:%M:%S UTC")
    inrelease = lists / "apt.example_dists_stable_InRelease"
    inrelease.write_text(
        f"Origin: Dmitri\nSuite: stable\nDate: {date}\nValid-Until: {date}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(updater_module, "APT_LIST_DIR", lists)
    with pytest.raises(updater_module.UpdateFailure, match="metadata_expired"):
        updater_module._verify_apt_metadata_dates("https://apt.example")


def test_metadata_list_name_matches_https_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import datetime

    lists = tmp_path / "lists"
    lists.mkdir()
    now = datetime.datetime.now(datetime.timezone.utc)
    issued = now.strftime("%a, %d %b %Y %H:%M:%S UTC")
    expiry = (now + datetime.timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S UTC")
    inrelease = lists / "apt.example:8443_dists_stable_InRelease"
    inrelease.write_text(
        f"Origin: Dmitri\nSuite: stable\nDate: {issued}\nValid-Until: {expiry}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(updater_module, "APT_LIST_DIR", lists)
    updater_module._verify_apt_metadata_dates("https://apt.example:8443")


def test_cached_target_still_refreshes_and_validates_signed_package_metadata(
    updater: Updater, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(updater_module, "PACKAGE_CACHE", cache)
    package = cache / "target.deb"
    package.write_bytes(b"cached target")
    digest = updater_module._sha256(package)
    package.rename(cache / f"{digest}.deb")
    package = cache / f"{digest}.deb"
    previous = cache / "1.2.2-1.deb"
    previous.write_bytes(b"cached previous")
    (cache / "1.2.2-1.sha256").write_text(
        updater_module._sha256(previous), encoding="ascii"
    )
    calls: list[str] = []
    deadline = (
        updater_module.datetime.now(updater_module.timezone.utc)
        .replace(year=2030)
        .isoformat()
    )
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.2-1")
    monkeypatch.setattr(
        updater, "_run_metadata_refresh", lambda: calls.append("refresh") or True
    )
    monkeypatch.setattr(
        updater_module,
        "_verify_apt_origin_suite",
        lambda version, sha: calls.append(f"verify:{version}:{sha}"),
    )
    monkeypatch.setattr(updater_module, "_verify_package", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_preflight", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_systemctl", lambda *_args: None)
    monkeypatch.setattr(updater, "_run_checked", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(updater, "_verify_local_health", lambda _target: "invocation")
    monkeypatch.setattr(
        updater,
        "_recover_update",
        lambda _update_id, _session_id, reason: {"reason": reason},
    )
    monkeypatch.setattr(updater, "_emit", lambda *_args, **_kwargs: None)
    posts: list[str] = []
    monkeypatch.setattr(
        updater,
        "_post_json",
        lambda path, _body: (
            posts.append(path)
            or {
                "update_id": "update",
                "session_id": "session",
                "release_id": "release",
                "sha256": digest,
                "target_package_version": "1.2.3-1",
                "required_updater_version": 1,
                "authorization_deadline": deadline,
            }
            if path.endswith("/claim")
            else {"ack_sequence": 1}
        ),
    )
    result = updater._apply_claimed_update(
        "update",
        "session",
        "release",
        "1.2.3-1",
        digest,
        updater_module.datetime.fromisoformat(deadline),
    )
    assert result == {"ok": True, "phase": "awaiting_confirmation"}, (
        result,
        calls,
        posts,
    )
    assert calls == ["refresh", f"verify:1.2.3-1:{digest}"]


@pytest.mark.parametrize("expire_during", ["event_send", "service_stop"])
def test_deadline_expiring_before_dpkg_never_starts_target_install(
    updater: Updater,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expire_during: str,
):
    class Clock(dt.datetime):
        current = dt.datetime.now(dt.timezone.utc)

        @classmethod
        def now(cls, tz=None):
            value = cls.current
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(updater_module, "datetime", Clock)
    cache = tmp_path / "cache"
    cache.mkdir()
    target_package = cache / "target.deb"
    target_package.write_bytes(b"target")
    target_digest = updater_module._sha256(target_package)
    target_package.rename(cache / f"{target_digest}.deb")
    target_package = cache / f"{target_digest}.deb"
    prior_package = cache / "1.2.2-1.deb"
    prior_package.write_bytes(b"prior")
    monkeypatch.setattr(updater_module, "PACKAGE_CACHE", cache)
    root = tmp_path / "agent-root"
    root.mkdir()
    (root / "runtime.txt").write_text("prior\n", encoding="ascii")
    monkeypatch.setattr(updater_module, "AGENT_ROOT", root)
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.2-1")
    monkeypatch.setattr(updater, "app_version", lambda: "1.2.2")
    monkeypatch.setattr(updater, "_run_metadata_refresh", lambda: True)
    monkeypatch.setattr(updater_module, "_verify_apt_origin_suite", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_verify_cache_digest", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_verify_package", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_preflight", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_cache_versioned_package", lambda *_args: None)
    monkeypatch.setattr(updater, "_verify_local_health", lambda _version: "rollback-id")
    deadline = Clock.current + dt.timedelta(seconds=30)
    commands = []
    events = []

    def systemctl(action, _service):
        if action == "stop" and expire_during == "service_stop":
            Clock.current = deadline + dt.timedelta(seconds=1)

    def run_checked(argv, **_kwargs):
        commands.append(argv)
        return ""

    def post(path, body):
        if path.endswith("/claim"):
            return {
                "update_id": "expire-stop",
                "session_id": "session",
                "release_id": "release",
                "sha256": target_digest,
                "target_package_version": "1.2.3-1",
                "required_updater_version": 1,
                "authorization_deadline": deadline.isoformat(),
            }
        events.append(body)
        if body["phase"] == "installing" and expire_during == "event_send":
            Clock.current = deadline + dt.timedelta(seconds=1)
        return {"ack_sequence": body["sequence"]}

    monkeypatch.setattr(updater_module, "_systemctl", systemctl)
    monkeypatch.setattr(updater, "_run_checked", run_checked)
    monkeypatch.setattr(updater, "_post_json", post)
    result = updater._apply_claimed_update(
        "expire-stop", "session", "release", "1.2.3-1", target_digest, deadline
    )

    assert result == {"ok": False, "error": "rolled_back"}
    assert not any(
        "--install" in command and "--force-downgrade" not in command
        for command in commands
    )
    assert any("--force-downgrade" in command for command in commands)
    assert [event["phase"] for event in events] == [
        "preparing",
        "installing",
        "recovering",
        "rolled_back",
    ]
    assert events[2]["error_code"] == "authorization_expired"
    assert events[2]["local_outcome"] is None


def test_expired_phase_has_no_local_outcome(updater: Updater, monkeypatch):
    calls = []
    monkeypatch.setattr(
        updater,
        "_emit",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    updater._expire_before_mutation("update", "session")
    assert calls[0][0][2:5] == ("expired", None, None)


def test_preclaim_expiry_is_local_only_and_survives_restart(
    updater: Updater, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class Clock(dt.datetime):
        current = dt.datetime.now(dt.timezone.utc)

        @classmethod
        def now(cls, tz=None):
            value = cls.current
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(updater_module, "datetime", Clock)
    cache = tmp_path / "preclaim-cache"
    cache.mkdir()
    target = cache / "target.deb"
    target.write_bytes(b"target")
    digest = updater_module._sha256(target)
    target.rename(cache / f"{digest}.deb")
    (cache / "1.2.2-1.deb").write_bytes(b"prior")
    monkeypatch.setattr(updater_module, "PACKAGE_CACHE", cache)
    monkeypatch.setattr(updater, "package_version", lambda: "1.2.2-1")
    monkeypatch.setattr(updater, "_run_metadata_refresh", lambda: True)
    monkeypatch.setattr(updater_module, "_verify_apt_origin_suite", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_verify_cache_digest", lambda *_args: None)
    monkeypatch.setattr(updater_module, "_verify_package", lambda *_args: None)

    deadline = Clock.current + dt.timedelta(seconds=1)

    def preflight(*_args):
        Clock.current = deadline + dt.timedelta(seconds=1)

    monkeypatch.setattr(updater_module, "_preflight", preflight)
    monkeypatch.setattr(updater_module, "_cache_versioned_package", lambda *_args: None)
    reporter_calls = []

    def post(path, _body):
        reporter_calls.append(path)
        pytest.fail("an unclaimed expired request must not be reported")

    monkeypatch.setattr(updater, "_post_json", post)
    monkeypatch.setattr(
        updater,
        "_run_checked",
        lambda *_args, **_kwargs: pytest.fail("dpkg must not run"),
    )
    update_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    release_id = str(uuid.uuid4())
    result = updater._apply_claimed_update(
        update_id, session_id, release_id, "1.2.3-1", digest, deadline
    )
    assert result == {"ok": False, "error": "authorization_expired"}
    assert reporter_calls == []

    with sqlite3.connect(updater.journal_path) as database:
        assert database.execute(
            "SELECT phase FROM operations WHERE operation_id=?", (update_id,)
        ).fetchone() == ("expired",)
        assert database.execute(
            "SELECT phase,error_code,sequence,pending_event FROM update_details "
            "WHERE operation_id=?",
            (update_id,),
        ).fetchone() == ("expired", "request_expired", 0, None)
        assert database.execute(
            "SELECT COUNT(*) FROM update_events WHERE operation_id=?", (update_id,)
        ).fetchone() == (0,)

    restarted = Updater(
        updater.state_dir,
        updater.runtime_dir,
        updater.gate_path,
        package_version=lambda: "1.2.2-1",
    )
    restarted.initialize()
    monkeypatch.setattr(restarted, "_post_json", post)
    assert restarted._apply_claimed_update(
        update_id,
        session_id,
        release_id,
        "1.2.3-1",
        digest,
        Clock.current + dt.timedelta(minutes=5),
    ) == {"ok": True, "phase": "expired", "replayed": True}
    assert reporter_calls == []


def test_metadata_expired_maps_to_metadata_expired_not_request_expired():
    assert (
        updater_module._failure_code(updater_module.UpdateFailure("metadata_expired"))
        == "metadata_expired"
    )


def test_reporter_403_pause_blocks_direct_flush(updater: Updater, monkeypatch):
    pause = updater.state_dir / "reporting-paused-403"
    pause.write_text("paused\n", encoding="ascii")
    monkeypatch.setattr(
        updater, "_post_json", lambda *_args: pytest.fail("403 pause bypassed")
    )
    updater._flush_events("missing-operation")


def test_claim_pending_retries_until_receipt_is_reconciled(
    updater: Updater, monkeypatch: pytest.MonkeyPatch
):
    with sqlite3.connect(updater.journal_path) as database:
        database.execute("INSERT INTO operations VALUES ('pending-claim', 'requested')")
        database.execute(
            "INSERT INTO update_details("
            "operation_id,session_id,release_id,target_version,"
            "sha256,deadline,phase) VALUES(?,?,?,?,?,?,?)",
            (
                "pending-claim",
                "session",
                "release",
                "1.2.3-1",
                "a" * 64,
                "2030-01-01T00:00:00+00:00",
                "claim_pending",
            ),
        )
    attempts = []

    def post(path, _body):
        attempts.append(path)
        raise OSError("offline")

    monkeypatch.setattr(updater, "_post_json", post)
    updater._reconcile_pending_claims()
    updater._reconcile_pending_claims()
    assert attempts == [
        "/api/v1/agent-updates/pending-claim/claim",
        "/api/v1/agent-updates/pending-claim/claim",
    ]
    with sqlite3.connect(updater.journal_path) as database:
        assert database.execute(
            "SELECT phase FROM update_details WHERE operation_id='pending-claim'"
        ).fetchone() == ("claim_pending",)


def test_update_failure_codes_match_backend_error_vocabulary():
    assert (
        updater_module._failure_code(updater_module.UpdateFailure("metadata_untrusted"))
        == "metadata_untrusted"
    )
    assert (
        updater_module._failure_code(
            updater_module.UpdateFailure("insufficient_resources")
        )
        == "insufficient_resources"
    )
    dpkg_failure = subprocess.CalledProcessError(
        1, ["/usr/bin/dpkg", "--install", "/tmp/hardware-agent.deb"]
    )
    assert updater_module._failure_code(dpkg_failure) == "install_failed"
    assert (
        updater_module._failure_code(
            updater_module.UpdateFailure("package_manager_busy")
        )
        == "package_manager_busy"
    )
