from __future__ import annotations

from typing import Any


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
