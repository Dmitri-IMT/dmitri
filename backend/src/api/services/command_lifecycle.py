"""Pure command lifecycle logic (no DB)."""
from __future__ import annotations

_LEGAL_EDGES: dict[str, set[str]] = {
    "queued": {"delivered", "expired"},
    "delivered": {"running", "expired"},
    "running": {"uploading", "failed"},
    "uploading": {"done", "failed"},
    "done": set(),
    "failed": set(),
    "expired": set(),
}

_SCAN_STATUS_BY_COMMAND_STATUS: dict[str, str] = {
    "queued": "pending",
    "delivered": "pending",
    "running": "accepted",
    "uploading": "processing",
    "done": "completed",
    "failed": "failed",
    "expired": "failed",
}


class InvalidCommandTransition(Exception):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition command from {current!r} to {target!r}")
        self.current = current
        self.target = target


def next_status(current: str, target: str) -> str:
    if target == current:
        return current
    if target not in _LEGAL_EDGES.get(current, set()):
        raise InvalidCommandTransition(current, target)
    return target


def scan_status_for(command_status: str) -> str:
    return _SCAN_STATUS_BY_COMMAND_STATUS[command_status]
