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

# Statuses an operator may still stop. `queued` lasts only inside the trigger
# request, and `uploading` already carries the results.
CANCELLABLE: tuple[str, ...] = ("delivered", "running")

# Scan statuses a command transition may still overwrite. Ingest owns the
# `completed` scan: once results land, the scan follows its data and the command
# follows the operator (spec 049, decision 3).
UNFINISHED_SCAN: tuple[str, ...] = ("pending", "accepted", "processing")

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


def accepts_late_ingest(status: str) -> bool:
    """A cancelled command still takes the partial results the Pi uploads."""
    return status == "cancelled"


def status_rank(status: str) -> int:
    return RANK[status]


def scan_status_for(command_status: str) -> str:
    return _SCAN_STATUS_BY_COMMAND_STATUS[command_status]
