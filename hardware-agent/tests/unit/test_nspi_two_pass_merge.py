"""Unit test for NSPi two-pass port scan merge in scan_ports_batch()."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.config import NSPI_HOST_TIMEOUT, NSPI_NSE_SCRIPTS, NSPI_PORTS, AgentSettings
from agent.discovery.port_discovery import scan_ports_batch
from agent.scanner.models import HostInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.stages import run_deep_inspection_stage


def _nmap_xml(ip: str, ports: list[int]) -> ET.Element:
    """Build minimal nmap XML with open TCP ports for a single host."""
    root = ET.Element("nmaprun")
    host = ET.SubElement(root, "host")
    status = ET.SubElement(host, "status")
    status.set("state", "up")
    address = ET.SubElement(host, "address")
    address.set("addr", ip)
    address.set("addrtype", "ipv4")
    port_elem = ET.SubElement(host, "ports")
    for p in ports:
        port = ET.SubElement(port_elem, "port")
        port.set("protocol", "tcp")
        port.set("portid", str(p))
        state = ET.SubElement(port, "state")
        state.set("state", "open")
        service = ET.SubElement(port, "service")
        service.set("name", "unknown")
    return root


def _make_nspi_runner(
    pass1_ports: list[int],
    pass2_ports: list[int],
    ip: str = "10.0.0.1",
    pass1_present: bool = True,
    pass2_present: bool = True,
) -> tuple[NmapRunner, list[list[str]]]:
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = "nmap"
    captured: list[list[str]] = []
    call_count = 0

    def _capture(arguments: list[str], timeout: float | None = None) -> ET.Element:
        nonlocal call_count
        captured.append(list(arguments))
        first_pass = call_count == 0
        ports = pass1_ports if first_pass else pass2_ports
        call_count += 1
        present = pass1_present if first_pass else pass2_present
        if not present:
            return ET.Element("nmaprun")
        return _nmap_xml(ip, ports)

    runner.run_xml = _capture  # type: ignore[assignment]
    return runner, captured


class TestNspiTwoPassMerge:
    def test_merged_ports_deduplicated(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22, 80, 445],
            pass2_ports=[445, 502],
        )
        results = scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        port_numbers = {p.port for p in results["10.0.0.1"].ports}
        assert port_numbers == {22, 80, 445, 502}

    def test_no_duplicate_ports(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22, 80, 445],
            pass2_ports=[445, 502],
        )
        results = scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        port_numbers = [p.port for p in results["10.0.0.1"].ports]
        assert len(port_numbers) == len(set(port_numbers))

    def test_nmap_called_twice(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22, 80, 445],
            pass2_ports=[445, 502],
        )
        scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        assert len(captured) == 2

    def test_pass1_has_no_port_flag(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22, 80, 445],
            pass2_ports=[445, 502],
        )
        scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        assert "-p" not in captured[0]

    def test_pass2_has_nspi_ports(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22, 80, 445],
            pass2_ports=[445, 502],
        )
        scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        p_idx = captured[1].index("-p")
        assert captured[1][p_idx + 1] == NSPI_PORTS

    def test_pass1_t4_pass2_t2_and_n(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
        )
        scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        assert "-T4" in captured[0]
        assert "-T2" not in captured[0]
        assert "-T2" in captured[1]
        assert "-T4" not in captured[1]
        for argv in captured:
            assert "-n" in argv

    def test_pass1_only_enumerates_ports(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
        )

        scan_ports_batch(runner, ["10.0.0.1"], "nspi")

        assert "-sV" not in captured[0]
        assert "-O" not in captured[0]

    def test_pass2_only_enumerates_ot_ports(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
        )

        scan_ports_batch(runner, ["10.0.0.1"], "nspi")

        assert "-sV" not in captured[1]
        assert "--script" not in captured[1]
        assert "-O" not in captured[1]

    def test_both_passes_have_per_host_timeout(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
        )

        scan_ports_batch(runner, ["10.0.0.1"], "nspi")

        for arguments in captured:
            timeout_index = arguments.index("--host-timeout")
            assert arguments[timeout_index + 1] == NSPI_HOST_TIMEOUT

    def test_completed_host_is_not_marked_skipped(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.skipped is False

    def test_host_missing_from_first_pass_is_marked_skipped(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
            pass1_present=False,
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.skipped is True
        assert [port.port for port in result.ports] == [502]

    def test_host_missing_from_second_pass_is_marked_skipped(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
            pass2_present=False,
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.skipped is True
        assert [port.port for port in result.ports] == [22]

    def test_merged_union_receives_one_authoritative_deep_enrichment(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22, 445],
            pass2_ports=[445, 502],
        )
        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]
        host = HostInfo(ip="10.0.0.1", hostname="host-one", ports=result.ports)

        run_deep_inspection_stage(
            runner,
            AgentSettings(scan_mode="nspi", max_workers=1),
            [host],
        )

        assert len(captured) == 3
        assert all("-sV" not in arguments for arguments in captured[:2])
        deep_arguments = captured[2]
        assert deep_arguments.count("-sV") == 1
        assert deep_arguments[deep_arguments.index("-p") + 1] == "22,445,502"
        assert deep_arguments[deep_arguments.index("--script") + 1] == ",".join(
            NSPI_NSE_SCRIPTS
        )
        assert "-O" in deep_arguments
