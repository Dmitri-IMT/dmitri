"""Unit tests for Quick mode nmap argument builder."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from agent.discovery.port_discovery import (
    discovery_arguments,
    scan_ports,
    scan_ports_batch,
)
from agent.normalize.contracts import ScanPayload
from agent.scanner.models import PortScanResult
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

    def _capture(arguments: list[str], timeout: float | None = None) -> ET.Element:
        captured.append(list(arguments))
        return EMPTY_NMAP_XML

    runner.run_xml = _capture  # type: ignore[assignment]
    return runner, captured


@pytest.mark.parametrize("scan_mode", ["quick", "standard", "extensive", "max"])
def test_single_host_scan_modes_return_port_scan_result(scan_mode: str) -> None:
    runner, _ = _make_capturing_runner()

    result = scan_ports(runner, "10.0.0.1", scan_mode)

    assert isinstance(result, PortScanResult)


@pytest.mark.parametrize(
    "scan_mode", ["quick", "standard", "extensive", "max", "nspi"]
)
def test_batch_scan_modes_return_port_scan_results(scan_mode: str) -> None:
    runner, _ = _make_capturing_runner()

    result = scan_ports_batch(runner, ["10.0.0.1"], scan_mode)

    assert isinstance(result["10.0.0.1"], PortScanResult)


@pytest.mark.parametrize(
    ("scan_mode", "expected_discovery_arguments"),
    [
        ("quick", ["-O"]),
        ("standard", ["-O"]),
        ("extensive", ["-O", "--top-ports", "10000"]),
        ("max", ["-O", "-p-", "--min-rate", "1000"]),
    ],
)
def test_single_and_batch_argv_remain_exact(
    scan_mode: str,
    expected_discovery_arguments: list[str],
) -> None:
    single_runner, single_calls = _make_capturing_runner()
    batch_runner, batch_calls = _make_capturing_runner()

    scan_ports(single_runner, "10.0.0.1", scan_mode)
    scan_ports_batch(batch_runner, ["10.0.0.1", "10.0.0.2"], scan_mode)

    assert single_calls == [
        ["-Pn", "-n", "-T4", *expected_discovery_arguments, "10.0.0.1"]
    ]
    assert batch_calls == [
        [
            "-Pn",
            "-n",
            "-T4",
            *expected_discovery_arguments,
            "10.0.0.1",
            "10.0.0.2",
        ]
    ]


class TestQuickModeArgv:
    def test_scan_ports_includes_required_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "quick")

        assert len(captured) == 1
        argv = captured[0]
        assert "-sV" not in argv
        assert "-O" in argv
        assert "--script" not in argv

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
        assert "-sV" not in argv
        assert "-O" in argv
        assert "--script" not in argv

    def test_scan_ports_batch_excludes_port_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports_batch(runner, ["10.0.0.1"], "quick")

        argv = captured[0]
        for flag in FORBIDDEN_PORT_FLAGS:
            assert flag not in argv, f"quick mode argv must not contain {flag}"


class TestStandardModeArgv:
    def test_scan_ports_defers_enrichment(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "standard")

        assert len(captured) == 1
        argv = captured[0]
        assert "-sV" not in argv
        assert "-O" in argv
        assert "--script" not in argv

    def test_scan_ports_batch_defers_enrichment(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports_batch(runner, ["10.0.0.1", "10.0.0.2"], "standard")

        assert len(captured) == 1
        argv = captured[0]
        assert "-sV" not in argv
        assert "-O" in argv
        assert "--script" not in argv

    def test_scan_ports_excludes_port_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "standard")

        argv = captured[0]
        for flag in FORBIDDEN_PORT_FLAGS:
            assert flag not in argv, f"standard mode argv must not contain {flag}"


class TestExtensiveModeArgv:
    def test_discovery_arguments_top_ports_no_scripts(self) -> None:
        assert discovery_arguments("extensive") == [
            "-O",
            "--top-ports",
            "10000",
        ]

    def test_discovery_arguments_unchanged_for_other_modes(self) -> None:
        assert discovery_arguments("quick") == ["-O"]

    def test_scan_ports_includes_top_ports_excludes_scripts(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "extensive")

        argv = captured[0]
        assert "-sV" not in argv
        assert "-O" in argv
        assert "--top-ports" in argv
        assert argv[argv.index("--top-ports") + 1] == "10000"
        assert "--script" not in argv
        assert "-p-" not in argv

    def test_scan_ports_batch_matches_single_discovery_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports_batch(runner, ["10.0.0.1", "10.0.0.2"], "extensive")

        argv = captured[0]
        assert "--top-ports" in argv
        assert argv[argv.index("--top-ports") + 1] == "10000"
        assert "--script" not in argv
        assert "-p-" not in argv

    def test_single_and_batch_share_discovery_flags(self) -> None:
        single_runner, single_cap = _make_capturing_runner()
        batch_runner, batch_cap = _make_capturing_runner()
        scan_ports(single_runner, "10.0.0.1", "extensive")
        scan_ports_batch(batch_runner, ["10.0.0.1"], "extensive")

        flags = ["-O", "--top-ports", "10000"]
        for flag in flags:
            assert flag in single_cap[0]
            assert flag in batch_cap[0]


class TestMaxModeArgv:
    def test_discovery_arguments_all_ports_min_rate_no_scripts(self) -> None:
        assert discovery_arguments("max") == [
            "-O",
            "-p-",
            "--min-rate",
            "1000",
        ]

    def test_scan_ports_includes_all_ports_excludes_scripts(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports(runner, "10.0.0.1", "max")

        argv = captured[0]
        assert "-sV" not in argv
        assert "-O" in argv
        assert "-p-" in argv
        assert argv[argv.index("--min-rate") + 1] == "1000"
        assert "--script" not in argv
        assert "--top-ports" not in argv

    def test_scan_ports_batch_matches_single_discovery_flags(self) -> None:
        runner, captured = _make_capturing_runner()
        scan_ports_batch(runner, ["10.0.0.1", "10.0.0.2"], "max")

        argv = captured[0]
        assert "-p-" in argv
        assert "--min-rate" in argv
        assert "--script" not in argv
        assert "--top-ports" not in argv


class TestStandardModeScanPayload:
    def test_scan_mode_is_top_level_field(self) -> None:
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="standard",
            hosts=[],
            findings=[],
        )
        dumped = payload.model_dump(mode="json")
        assert "scan_mode" in dumped
        assert dumped["scan_mode"] == "standard"

    def test_scan_mode_not_nested_under_metadata(self) -> None:
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="standard",
            hosts=[],
            findings=[],
            metadata={"elapsed_seconds": 5.0},
        )
        dumped = payload.model_dump(mode="json")
        assert "scan_mode" not in (dumped.get("metadata") or {})
        assert dumped["scan_mode"] == "standard"


class TestQuickModeScanPayload:
    def test_scan_mode_is_top_level_field(self) -> None:
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="quick",
            hosts=[],
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
            hosts=[],
            findings=[],
            metadata={"elapsed_seconds": 5.0},
        )
        dumped = payload.model_dump(mode="json")
        assert "scan_mode" not in (dumped.get("metadata") or {})
        assert dumped["scan_mode"] == "quick"
