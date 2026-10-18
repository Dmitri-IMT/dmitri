"""Shared admission lease for scans and the appliance updater.

Scans take a nonblocking shared flock on the stable appliance lock inode. The
updater takes the same inode exclusively. The descriptor can be deliberately
inherited by scan subprocesses so an orphaned child continues to block updates.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_PATH_FILE = Path("/usr/lib/dmitri/scan-lock-path")
UPDATE_GATE_PATH = Path("/var/lib/dmitri/update-gate.json")


def _is_source_checkout() -> bool:
    """Return whether this module is imported from the repository source tree.

    Distribution metadata is intentionally not used: editable installs and
    stale/incomplete ``.dist-info`` directories make it unreliable for
    distinguishing a checkout from an installed appliance package.
    """
    module_path = Path(__file__).resolve()
    checkout_root = module_path.parents[3]
    source_package = (checkout_root / "src" / "agent").resolve()
    try:
        module_path.relative_to(source_package)
    except ValueError:
        return False
    return True


def scan_lock_path() -> Path | None:
    # Source checkouts have no appliance updater and retain their existing
    # behavior. Packaged installs provide this fixed-path contract.
    if not LOCK_PATH_FILE.exists():
        if _is_source_checkout():
            return None
        raise FileNotFoundError(
            f"Appliance scan lock contract is missing: {LOCK_PATH_FILE}"
        )
    value = LOCK_PATH_FILE.read_text(encoding="utf-8").strip()
    if not value:
        raise OSError("Appliance scan lock path is empty.")
    path = Path(value)
    if not path.is_absolute():
        raise OSError("Appliance scan lock path must be absolute.")
    return path


class UpgradeInProgressError(Exception):
    """The appliance updater or a stale installation prevents scan admission."""


class ScanLease:
    """An acquired scan lease; borrowed users must not close the owner's lease."""

    def __init__(self, descriptor: int | None, path: Path | None) -> None:
        self._descriptor = descriptor
        self.path = path
        self._closed = False

    @property
    def pass_fds(self) -> tuple[int, ...]:
        if self._closed or self._descriptor is None:
            return ()
        return (self._descriptor,)

    @property
    def active(self) -> bool:
        return not self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None


def _check_update_gate() -> None:
    # Presence is the durable blocked signal. Invalid JSON is also blocking:
    # scans must not infer that a damaged gate is safe to ignore.
    if UPDATE_GATE_PATH.exists():
        try:
            gate = json.loads(UPDATE_GATE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UpgradeInProgressError(
                "Agent update recovery is required; scans are blocked."
            ) from exc
        if not isinstance(gate, dict) or gate.get("blocked") is not True:
            raise UpgradeInProgressError(
                "Agent update state is unresolved; scans are blocked."
            )
        raise UpgradeInProgressError("Agent update in progress; try again later.")


def _check_installation_identity() -> None:
    # The imported process identity is captured when the agent modules load;
    # package metadata changes during an update, so stale idle TUI/daemon
    # processes must not start new scans from an old in-memory code tree.
    from agent.version import PROCESS_START_VERSION, installed_version

    try:
        current = installed_version()
    except Exception as exc:
        raise UpgradeInProgressError(
            "Installed agent identity cannot be verified; scans are blocked."
        ) from exc
    if current != PROCESS_START_VERSION:
        raise UpgradeInProgressError(
            "Agent code is stale after an update; restart it before scanning."
        )


def acquire_scan_lease() -> ScanLease:
    if sys.platform == "win32":
        return ScanLease(None, None)

    path = scan_lock_path()
    if path is None:
        return ScanLease(None, None)

    import fcntl

    # Do not create or replace the path: all participants must lock one inode.
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.set_inheritable(descriptor, False)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UpgradeInProgressError(
                "Agent update in progress; try again later."
            ) from exc
        _check_update_gate()
        _check_installation_identity()
        return ScanLease(descriptor, path)
    except BaseException:
        os.close(descriptor)
        raise


@contextmanager
def scan_lock(lease: ScanLease | None = None) -> Iterator[ScanLease]:
    """Own a new lease, or borrow the explicit lease supplied by an outer flow."""
    if lease is not None:
        if not lease.active:
            raise OSError("Cannot borrow a released scan lease.")
        yield lease
        return

    owned = acquire_scan_lease()
    try:
        yield owned
    finally:
        owned.close()
