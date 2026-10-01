from __future__ import annotations

from typing import Any, Literal, cast, get_args

# Why the Pi runner ended a scan (`metadata.terminated_by`).
TerminatedBy = Literal["completed", "user_cancel", "timeout", "error"]


def scan_duration_seconds(
    status: str, metadata: dict[str, Any] | None
) -> int | None:
    if status != "completed":
        return None
    if not metadata:
        return None
    raw = metadata.get("elapsed_seconds")
    if raw is None:
        return None
    if not isinstance(raw, (int, float)):
        return None
    seconds = int(raw)
    return seconds if seconds >= 0 else None


def scan_terminated_by(metadata: dict[str, Any] | None) -> TerminatedBy | None:
    raw = (metadata or {}).get("terminated_by")
    if raw not in get_args(TerminatedBy):
        return None
    return cast(TerminatedBy, raw)
