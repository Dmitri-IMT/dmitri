"""Unit test for NSPi two-pass port scan merge in scan_ports_batch()."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.config import NSPI_PORTS
from agent.discovery.port_discovery import scan_ports_batch
from agent.scanner.models import OperatingSystemInfo
from agent.scanner.nmap import NmapRunner


def _nmap_xml(
    ip: str,
    ports: list[int],
    operating_system: tuple[str, int] | None = None,
) -> ET.Element:
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
    if operating_system is not None:
        os_element = ET.SubElement(host, "os")
        ET.SubElement(
            os_element,
            "osmatch",
            name=operating_system[0],
            accuracy=str(operating_system[1]),
        )
    return root


def _make_nspi_runner(
    pass1_ports: list[int],
    pass2_ports: list[int],
    ip: str = "10.0.0.1",
    pass1_os: tuple[str, int] | None = None,
    pass2_os: tuple[str, int] | None = None,
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
        operating_system = pass1_os if first_pass else pass2_os
        call_count += 1
        return _nmap_xml(ip, ports, operating_system)

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

    def test_pass2_without_os_retains_pass1_detection(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
            pass1_os=("Linux", 96),
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.operating_system == OperatingSystemInfo(
            name="Linux", accuracy=96
        )

    def test_pass2_detection_is_used_when_pass1_has_none(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
            pass2_os=("Embedded Linux", 87),
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.operating_system == OperatingSystemInfo(
            name="Embedded Linux", accuracy=87
        )

    def test_stronger_pass2_detection_replaces_pass1(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
            pass1_os=("Linux", 85),
            pass2_os=("Embedded Linux", 97),
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.operating_system == OperatingSystemInfo(
            name="Embedded Linux", accuracy=97
        )

    def test_equal_pass2_detection_retains_existing_detection(self) -> None:
        runner, _ = _make_nspi_runner(
            pass1_ports=[22],
            pass2_ports=[502],
            pass1_os=("First", 90),
            pass2_os=("Second", 90),
        )

        result = scan_ports_batch(runner, ["10.0.0.1"], "nspi")["10.0.0.1"]

        assert result.operating_system == OperatingSystemInfo(
            name="First", accuracy=90
        )
