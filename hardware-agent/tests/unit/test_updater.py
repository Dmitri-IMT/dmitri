from __future__ import annotations

import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "packaging/updater.py"
SPEC = importlib.util.spec_from_file_location("dmitri_updater", MODULE_PATH)
updater_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(updater_module)
Updater = updater_module.Updater


@pytest.fixture
def updater(tmp_path: Path) -> Updater:
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
            ["/usr/bin/apt-get", "update"],
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
    client.sendall(b'{"command":"inspect"}\n{"command":"check"}')
    client.shutdown(socket.SHUT_WR)
    worker = threading.Thread(target=updater._handle_connection, args=(server,))
    worker.start()
    response = json.loads(client.recv(1024))
    client.close()
    worker.join(timeout=1)
    assert response == {"ok": False, "error": "invalid_request"}


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
