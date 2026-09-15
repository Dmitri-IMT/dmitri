from __future__ import annotations

from typing import get_args

from api.core.error_codes import (
    SCAN_ERROR_CODES,
    ScanErrorCode,
    normalise_error_code,
    scan_error_code,
)

PUBLISHED = (
    "device_offline",
    "device_busy",
    "agent_disconnected",
    "scan_failed",
    "scan_timeout",
    "invalid_command",
    "result_unavailable",
    "ingest_failed",
    "unknown",
)


def test_published_codes_round_trip():
    for code in PUBLISHED:
        assert normalise_error_code(code) == code


def test_null_stays_null():
    assert normalise_error_code(None) is None


def test_off_contract_string_normalises_to_unknown():
    assert normalise_error_code("warp_core_breach") == "unknown"


def test_set_is_exactly_nine_literal_members():
    assert len(SCAN_ERROR_CODES) == 9
    assert SCAN_ERROR_CODES == frozenset(get_args(ScanErrorCode))
    assert SCAN_ERROR_CODES == frozenset(PUBLISHED)


def test_non_failed_scan_carries_nothing():
    for status in ("pending", "accepted", "processing", "completed"):
        assert scan_error_code(status, "scan_failed") is None


def test_failed_scan_is_never_bare():
    assert scan_error_code("failed", None) == "unknown"
    assert scan_error_code("failed", "warp_core_breach") == "unknown"
