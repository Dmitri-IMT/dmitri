from __future__ import annotations

import sys

import pytest
from agent.scanner.runner import ScanRunner
from agent.scanner.scan_lock import scan_lock_path

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX")


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


def test_a_running_scan_blocks_the_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []
    runner = ScanRunner("192.168.1.0/24", "quick")
    monkeypatch.setattr(runner, "_run", lambda: seen.append(_upgrade_can_lock()))

    runner.run_blocking()

    assert seen == [False]
    assert _upgrade_can_lock()


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


def test_missing_appliance_lock_fails_closed(monkeypatch):
    errors = []
    calls = []
    scan_lock_path().unlink()
    runner = ScanRunner("192.168.1.0/24", "quick", on_error=errors.append)
    monkeypatch.setattr(runner, "_run", lambda: calls.append(True))
    runner.run_blocking()
    assert isinstance(errors[0], FileNotFoundError)
    assert calls == []
