"""A shared file lock held for the whole life of one scan.

packaging/apt-upgrade-agent takes the same file exclusively and skips the
upgrade while any scan holds it: the upgrade restarts dmitri-agent, and a
restart drops the in-process scan ledger (ADR-021 §3).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from agent.paths import default_results_dir


def scan_lock_path() -> Path:
    # dmitri-agent.service sets XDG_DATA_HOME=/var/lib/dmitri, so on the Pi this
    # is /var/lib/dmitri/dmitri/scan.lock, the path apt-upgrade-agent locks.
    return Path(default_results_dir()).parent / "scan.lock"


@contextmanager
def scan_lock() -> Iterator[None]:
    if sys.platform == "win32":
        # No package upgrade runs on Windows, so nothing waits on this lock.
        yield
        return
    import fcntl

    path = scan_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        # Shared: scans do not block each other, only the upgrade.
        fcntl.flock(handle, fcntl.LOCK_SH)
        yield
