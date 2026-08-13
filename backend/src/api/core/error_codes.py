from __future__ import annotations

from typing import Literal, get_args

ScanErrorCode = Literal[
    "device_offline",
    "device_busy",
    "agent_disconnected",
    "scan_failed",
    "invalid_command",
    "result_unavailable",
    "ingest_failed",
    "unknown",
]

SCAN_ERROR_CODES: frozenset[str] = frozenset(get_args(ScanErrorCode))

UNKNOWN: ScanErrorCode = "unknown"


def normalise_error_code(stored: str | None) -> ScanErrorCode | None:
    """Map a stored command error code onto the published set.

    NULL stays NULL; a code outside the published set becomes ``unknown``. The
    column is free text, so a newer Pi reporting a code this build has never
    heard of must degrade to ``unknown`` rather than break the response.
    """
    if stored is None:
        return None
    return stored if stored in SCAN_ERROR_CODES else UNKNOWN


def scan_error_code(scan_status: str, stored: str | None) -> ScanErrorCode | None:
    """The scan-detail rule: a failed scan always carries a reason, others never do."""
    if scan_status != "failed":
        return None
    return normalise_error_code(stored) or UNKNOWN
