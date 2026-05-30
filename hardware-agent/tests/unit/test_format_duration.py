"""Tests for agent.tui.screens.scan_view.format_duration — tiered duration display."""

from __future__ import annotations

import pytest
from agent.tui.screens.scan_view import format_duration


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0s"),
        (0.4, "0s"),
        (12, "12s"),
        (59, "59s"),
        (59.6, "1m 00s"),
        (60, "1m 00s"),
        (83, "1m 23s"),
        (119.9, "2m 00s"),
        (600, "10m 00s"),
        (3599.7, "1h 00m 00s"),
        (3600, "1h 00m 00s"),
        (3661, "1h 01m 01s"),
        (7325, "2h 02m 05s"),
    ],
)
def test_format_duration(seconds: float, expected: str) -> None:
    assert format_duration(seconds) == expected
