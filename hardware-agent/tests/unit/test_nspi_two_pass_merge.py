"""Unit test for NSPi two-pass port scan merge in scan_ports_batch()."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.config import NSPI_PORTS
from agent.discovery.port_discovery import scan_ports_batch
from agent.scanner.nmap import NmapRunner


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
) -> tuple[NmapRunner, list[list[str]]]:
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = "nmap"
    captured: list[list[str]] = []
    call_count = 0

    def _capture(arguments: list[str], timeout: float | None = None) -> ET.Element:
        nonlocal call_count
        captured.append(list(arguments))
        ports = pass1_ports if call_count == 0 else pass2_ports
        call_count += 1
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
        port_numbers = {p.port for p in results["10.0.0.1"]}
        assert port_numbers == {22, 80, 445, 502}

    def test_no_duplicate_ports(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22, 80, 445],
            pass2_ports=[445, 502],
        )
        results = scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        port_numbers = [p.port for p in results["10.0.0.1"]]
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

    def test_both_passes_use_t2_and_n(self) -> None:
        runner, captured = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
        )
        scan_ports_batch(runner, ["10.0.0.1"], "nspi")
        for argv in captured:
            assert "-T2" in argv
            assert "-n" in argv
