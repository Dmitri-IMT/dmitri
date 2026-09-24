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
