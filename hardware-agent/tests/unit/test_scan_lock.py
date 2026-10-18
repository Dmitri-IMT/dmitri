from __future__ import annotations

import sys

import pytest
from agent.scanner.runner import ScanRunner
from agent.scanner.scan_lock import scan_lock_path

POSIX_FLOCK = pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX")


def _upgrade_can_lock() -> bool:
    """Take the lock the way apt-upgrade-agent does: exclusive, non-blocking."""
    import fcntl

    scan_lock_path().parent.mkdir(parents=True, exist_ok=True)
    with scan_lock_path().open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


@POSIX_FLOCK
def test_a_running_scan_blocks_the_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []
    runner = ScanRunner("192.168.1.0/24", "quick")
    monkeypatch.setattr(runner, "_run", lambda: seen.append(_upgrade_can_lock()))

    runner.run_blocking()

    assert seen == [False]
    assert _upgrade_can_lock()


@POSIX_FLOCK
@pytest.mark.parametrize("threaded", [False, True], ids=["headless", "tui"])
def test_upgrade_refuses_scan_without_waiting(monkeypatch, threaded) -> None:
    import fcntl

    from agent.scanner.scan_lock import UpgradeInProgressError

    errors = []
    calls = []
    runner = ScanRunner("192.168.1.0/24", "quick", on_error=errors.append)
    monkeypatch.setattr(runner, "_run", lambda: calls.append(True))
    with scan_lock_path().open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Use a worker in both cases so a blocking regression fails, not hangs.
        import threading

        worker = threading.Thread(
            target=runner.start if threaded else runner.run_blocking
        )
        worker.start()
        worker.join(timeout=1)
        if threaded:
            runner._thread.join(timeout=1)
        refused = bool(errors)
    worker.join(timeout=1)
    if threaded:
        runner._thread.join(timeout=1)
    assert refused
    assert isinstance(errors[0], UpgradeInProgressError)
    assert calls == []


def test_lock_path_does_not_depend_on_results(monkeypatch):
    path = scan_lock_path()
    monkeypatch.setenv("XDG_DATA_HOME", "/some/other/results")
    assert scan_lock_path() == path


@POSIX_FLOCK
def test_missing_appliance_lock_fails_closed(monkeypatch):
    errors = []
    calls = []
    scan_lock_path().unlink()
    runner = ScanRunner("192.168.1.0/24", "quick", on_error=errors.append)
    monkeypatch.setattr(runner, "_run", lambda: calls.append(True))
    runner.run_blocking()
    assert isinstance(errors[0], FileNotFoundError)
    assert calls == []


@POSIX_FLOCK
def test_installed_package_missing_contract_fails_closed_even_with_gate(
    monkeypatch, tmp_path
):
    from agent.scanner import scan_lock

    contract = tmp_path / "missing-contract"
    gate = tmp_path / "update-gate.json"
    gate.write_text('{"blocked":true,"reason":"recovery_required"}')
    monkeypatch.setattr(scan_lock, "LOCK_PATH_FILE", contract)
    monkeypatch.setattr(scan_lock, "UPDATE_GATE_PATH", gate)
    monkeypatch.setattr(scan_lock, "_is_source_checkout", lambda: False)

    errors = []
    calls = []
    runner = ScanRunner("192.168.1.0/24", "quick", on_error=errors.append)
    monkeypatch.setattr(runner, "_run", lambda: calls.append(True))

    runner.run_blocking()

    assert calls == []
    assert len(errors) == 1
    assert isinstance(errors[0], FileNotFoundError)
    assert "Appliance scan lock contract is missing" in str(errors[0])


def test_borrowed_lease_is_reused_without_becoming_owner():
    from agent.scanner.scan_lock import ScanLease, scan_lock

    lease = ScanLease(None, None)
    with scan_lock(lease) as borrowed:
        assert borrowed is lease
        assert lease.active
    assert lease.active
    lease.close()
    assert not lease.active


def test_persistent_gate_blocks_even_without_live_update_process(
    monkeypatch, tmp_path
):
    from agent.scanner import scan_lock

    gate = tmp_path / "update-gate.json"
    gate.write_text(
        '{"blocked":true,"reason":"recovery_required","operation_ids":[]}'
    )
    monkeypatch.setattr(scan_lock, "UPDATE_GATE_PATH", gate)
    with pytest.raises(scan_lock.UpgradeInProgressError, match="update in progress"):
        scan_lock._check_update_gate()


@POSIX_FLOCK
def test_scan_runner_refuses_persistent_gate_before_scan_body(monkeypatch, tmp_path):
    from agent.scanner import scan_lock
    from agent.scanner.scan_lock import UpgradeInProgressError

    gate = tmp_path / "update-gate.json"
    gate.write_text(
        '{"blocked":true,"reason":"recovery_required","operation_ids":[]}'
    )
    monkeypatch.setattr(scan_lock, "UPDATE_GATE_PATH", gate)
    errors = []
    calls = []
    runner = ScanRunner("192.168.1.0/24", "quick", on_error=errors.append)
    monkeypatch.setattr(runner, "_run", lambda: calls.append(True))

    runner.run_blocking()

    assert calls == []
    assert len(errors) == 1
    assert isinstance(errors[0], UpgradeInProgressError)


def test_source_checkout_without_appliance_contract_remains_unlocked(
    monkeypatch, tmp_path
):
    from agent.scanner import scan_lock

    monkeypatch.setattr(scan_lock, "LOCK_PATH_FILE", tmp_path / "missing-contract")
    gate = tmp_path / "update-gate.json"
    gate.write_text("corrupt gate ignored outside appliance mode")
    monkeypatch.setattr(scan_lock, "UPDATE_GATE_PATH", gate)
    assert scan_lock._is_source_checkout()

    with scan_lock.scan_lock() as lease:
        assert lease.active
        assert lease.pass_fds == ()


def test_corrupt_gate_fails_closed(monkeypatch, tmp_path):
    from agent.scanner import scan_lock

    gate = tmp_path / "update-gate.json"
    gate.write_text("not-json")
    monkeypatch.setattr(scan_lock, "UPDATE_GATE_PATH", gate)
    with pytest.raises(scan_lock.UpgradeInProgressError, match="recovery is required"):
        scan_lock._check_update_gate()


def test_stale_process_version_cannot_admit_scan(monkeypatch):
    from agent import version
    from agent.scanner import scan_lock

    monkeypatch.setattr(version, "PROCESS_START_VERSION", "1.0.0")
    monkeypatch.setattr(version, "installed_version", lambda: "1.0.1")
    with pytest.raises(scan_lock.UpgradeInProgressError, match="code is stale"):
        scan_lock._check_installation_identity()


@POSIX_FLOCK
def test_child_inherits_lease_fd_until_it_exits():
    import fcntl
    import subprocess
    import sys

    from agent.scanner.scan_lock import acquire_scan_lease, scan_lock_path

    lease = acquire_scan_lease()
    assert lease.pass_fds
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.4)"],
        pass_fds=lease.pass_fds,
    )
    try:
        lease.close()
        with scan_lock_path().open("r") as handle:
            with pytest.raises(BlockingIOError):
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        process.wait(timeout=3)
        with scan_lock_path().open("r") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
        lease.close()
