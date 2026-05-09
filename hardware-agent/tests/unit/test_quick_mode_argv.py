"""Unit tests for Quick mode nmap argument builder."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from agent.discovery.port_discovery import scan_ports, scan_ports_batch
from agent.normalize.contracts import ScanPayload
from agent.scanner.nmap import NmapRunner

EMPTY_NMAP_XML = ET.fromstring(
    "<nmaprun><runstats><finished /><hosts /></runstats></nmaprun>"
)

FORBIDDEN_PORT_FLAGS = {"-F", "-p", "--top-ports"}


def _make_capturing_runner() -> tuple[NmapRunner, list[list[str]]]:
    """Return a runner whose run_xml records each call's arguments."""
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = "nmap"
    captured: list[list[str]] = []

    def _capture(arguments: list[str]) -> ET.Element:
        captured.append(list(arguments))
        return EMPTY_NMAP_XML

    runner.run_xml = _capture  # type: ignore[assignment]
    return runner, captured


class TestQuickModeArgv:
    def test_scan_ports_includes_required_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "quick")

        assert len(captured) == 1
        argv = captured[0]
        assert "-sV" in argv
        assert "-O" in argv
        assert "--script" in argv
        script_idx = argv.index("--script")
        assert argv[script_idx + 1] == "vulners"

    def test_scan_ports_excludes_port_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "quick")

        argv = captured[0]
        for flag in FORBIDDEN_PORT_FLAGS:
            assert flag not in argv, f"quick mode argv must not contain {flag}"

    def test_scan_ports_batch_includes_required_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports_batch(runner, ["10.0.0.1", "10.0.0.2"], "quick")

        assert len(captured) == 1
        argv = captured[0]
        assert "-sV" in argv
        assert "-O" in argv
        assert "--script" in argv
        script_idx = argv.index("--script")
        assert argv[script_idx + 1] == "vulners"

    def test_scan_ports_batch_excludes_port_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports_batch(runner, ["10.0.0.1"], "quick")

        argv = captured[0]
        for flag in FORBIDDEN_PORT_FLAGS:
            assert flag not in argv, f"quick mode argv must not contain {flag}"

    def test_full_mode_does_not_get_quick_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "full")

        argv = captured[0]
        assert "-p-" in argv
        assert "-sV" not in argv
        assert "-O" not in argv
        assert "--script" not in argv


class TestQuickModeScanPayload:
    def test_scan_mode_is_top_level_field(self) -> None:
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="quick",
            devices=[],
            findings=[],
        )
        dumped = payload.model_dump(mode="json")
        assert "scan_mode" in dumped
        assert dumped["scan_mode"] == "quick"

    def test_scan_mode_not_nested_under_metadata(self) -> None:
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="quick",
            devices=[],
            findings=[],
            metadata={"elapsed_seconds": 5.0},
        )
        dumped = payload.model_dump(mode="json")
        assert "scan_mode" not in (dumped.get("metadata") or {})
        assert dumped["scan_mode"] == "quick"
