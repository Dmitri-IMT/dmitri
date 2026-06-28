"""Unit tests for per-call subprocess timeout resolver and resilience config knobs."""

from __future__ import annotations

import pytest
from agent.config import AgentSettings, subprocess_timeout_for

EXPECTED_TIMEOUTS = [
    ("quick", "discovery", 600.0),
    ("standard", "discovery", 600.0),
    ("extensive", "discovery", 600.0),
    ("nspi", "discovery", 600.0),
    ("max", "discovery", 600.0),
    ("quick", "ports", 600.0),
    ("standard", "ports", 900.0),
    ("extensive", "ports", 1800.0),
    ("nspi", "ports", 600.0),
    ("max", "ports", 3600.0),
    ("quick", "nse", 900.0),
    ("standard", "nse", 1200.0),
    ("extensive", "nse", 2400.0),
    ("nspi", "nse", 1200.0),
    ("max", "nse", 3600.0),
]


class TestSubprocessTimeoutFor:
    @pytest.mark.parametrize("mode, stage, expected", EXPECTED_TIMEOUTS)
    def test_returns_documented_value(
        self, mode: str, stage: str, expected: float
    ) -> None:
        result = subprocess_timeout_for(mode, stage)
        assert result == expected
        assert isinstance(result, float)


class TestResilienceConfigDefaults:
    def test_scan_deadline_default(self) -> None:
        assert AgentSettings().scan_deadline_s == 0

    def test_unit_failure_threshold_default(self) -> None:
        assert AgentSettings().unit_failure_threshold == 0.5

    def test_transient_retries_default(self) -> None:
        assert AgentSettings().transient_retries == 1
