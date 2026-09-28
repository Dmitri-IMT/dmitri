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

LOCK_PATH_FILE = Path("/usr/lib/dmitri/scan-lock-path")


def scan_lock_path() -> Path | None:
    # The package installs this contract for Python and both shell entrypoints.
    # Source checkouts have no appliance updater and need no system lock.
    if not LOCK_PATH_FILE.exists():
        return None
    return Path(LOCK_PATH_FILE.read_text().strip())


class UpgradeInProgressError(Exception):
    pass


@contextmanager
def scan_lock() -> Iterator[None]:
    if sys.platform == "win32":
        # No package upgrade runs on Windows, so nothing waits on this lock.
        yield
        return
    import fcntl

    path = scan_lock_path()
    if path is None:
        yield
        return
    # Packaging creates the file; read access lets unprivileged TUI scans join.
    # Do not recreate it: replacing the inode would split the lock protocol.
    with path.open("r") as handle:
        # Shared: scans do not block each other, only the upgrade.
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UpgradeInProgressError(
                "Agent update in progress; try again later."
            ) from exc
        yield
