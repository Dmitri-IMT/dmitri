from __future__ import annotations

from api.core.scan_read import scan_duration_seconds


def test_completed_integer_elapsed_seconds() -> None:
    assert scan_duration_seconds("completed", {"elapsed_seconds": 45}) == 45


def test_completed_float_elapsed_seconds_truncates() -> None:
    assert scan_duration_seconds("completed", {"elapsed_seconds": 187.9}) == 187


def test_completed_missing_key() -> None:
    assert scan_duration_seconds("completed", {}) is None
    assert scan_duration_seconds("completed", None) is None


def test_non_completed_statuses_have_no_duration() -> None:
    metadata = {"elapsed_seconds": 45}
    for status in ("failed", "pending", "processing", "accepted"):
        assert scan_duration_seconds(status, metadata) is None


def test_non_numeric_elapsed_seconds() -> None:
    assert scan_duration_seconds("completed", {"elapsed_seconds": "45"}) is None


def test_negative_elapsed_seconds() -> None:
    assert scan_duration_seconds("completed", {"elapsed_seconds": -1}) is None
