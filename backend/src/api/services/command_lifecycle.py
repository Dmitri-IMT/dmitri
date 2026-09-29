"""Pure command lifecycle logic (no DB)."""
from __future__ import annotations

# The canonical command status domain. `services/commands.py` builds its SQL
# rank expression and status filters from these, so the Python rule and the
# SQL rule cannot drift apart.
RANK: dict[str, int] = {
    "queued": 0,
    "delivered": 1,
    "running": 2,
    "uploading": 3,
    "done": 4,
    "failed": 4,
    "cancelled": 4,
    "expired": 4,
}

# Statuses only a Pi may report over the command channel.
PI_OWNED = frozenset({"running", "uploading", "done", "failed", "cancelled"})

TERMINAL = frozenset({"done", "failed", "cancelled", "expired"})

# The "agent is busy" set, matching the partial-unique-index predicate in
# alembic/versions/20260731_13_command_delivery.py.
NON_TERMINAL: tuple[str, ...] = tuple(s for s in RANK if s not in TERMINAL)

_SCAN_STATUS_BY_COMMAND_STATUS: dict[str, str] = {
    "queued": "pending",
    "delivered": "pending",
    "running": "accepted",
    "uploading": "processing",
    "done": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "expired": "failed",
}


def is_terminal(status: str) -> bool:
    return status in TERMINAL


def status_rank(status: str) -> int:
    return RANK[status]


def scan_status_for(command_status: str) -> str:
    return _SCAN_STATUS_BY_COMMAND_STATUS[command_status]
