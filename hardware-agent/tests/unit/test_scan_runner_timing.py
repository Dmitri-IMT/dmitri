"""Regression test for ScanRunner duration capture (issue #67).

The TUI used to hardcode elapsed_seconds=0; this asserts it now measures
real wall-clock time via an injected fake runner.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET

import pytest
from agent.normalize.contracts import ScanPayload
from agent.scanner.nmap import NmapRunner
from agent.tui.scanner import ScanRunner


class _FakeRunner(NmapRunner):
    """Returns an empty nmaprun and burns a little wall-clock time per call."""

    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        time.sleep(0.02)
        return ET.fromstring("<nmaprun/>")


def test_elapsed_seconds_is_captured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent.tui.scanner.check_network_connectivity", lambda: None)
    captured: dict[str, ScanPayload] = {}

    runner = ScanRunner(
        subnet="192.168.1.0/24",
        scan_mode="standard",
        on_complete=lambda payload: captured.update(payload=payload),
        runner=_FakeRunner(),
    )
    runner._run()

    payload = captured["payload"]
    assert payload.metadata["elapsed_seconds"] > 0
