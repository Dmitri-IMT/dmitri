"""Forwarding coverage for resolved per-call timeouts (spec 010, Task 5)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.discovery.network_discovery import discover_hosts
from agent.discovery.port_discovery import scan_ports_batch
from agent.discovery.vulnerability_detection import run_nse_vulnerability_scan
from agent.scanner.models import PortInfo
from agent.scanner.nmap import NmapRunner


class _SpyRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"
        self.timeouts: list[float | None] = []

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        self.timeouts.append(timeout)
        return ET.fromstring("<nmaprun/>")


class TestDiscoverHostsTimeout:
    def test_forwards_explicit_timeout(self) -> None:
        spy = _SpyRunner()
        discover_hosts(spy, "10.0.0.0/24", timeout=12.0)
        assert spy.timeouts == [12.0]

    def test_default_timeout_is_none(self) -> None:
        spy = _SpyRunner()
        discover_hosts(spy, "10.0.0.0/24")
        assert spy.timeouts == [None]


class TestScanPortsBatchTimeout:
    def test_standard_forwards_explicit_timeout(self) -> None:
        spy = _SpyRunner()
        scan_ports_batch(spy, ["10.0.0.1"], "standard", timeout=34.0)
        assert spy.timeouts == [34.0]

    def test_standard_default_timeout_is_none(self) -> None:
        spy = _SpyRunner()
        scan_ports_batch(spy, ["10.0.0.1"], "standard")
        assert spy.timeouts == [None]

    def test_nspi_forwards_timeout_to_both_passes(self) -> None:
        spy = _SpyRunner()
        scan_ports_batch(spy, ["10.0.0.1"], "nspi", timeout=34.0)
        assert spy.timeouts == [34.0, 34.0]


class TestRunNseVulnerabilityScanTimeout:
    def test_forwards_explicit_timeout(self) -> None:
        spy = _SpyRunner()
        run_nse_vulnerability_scan(
            spy,
            "10.0.0.1",
            [PortInfo(port=22)],
            version_intensity=2,
            scripts=("vulners",),
            min_cvss=0.0,
            timeout=56.0,
        )
        assert spy.timeouts == [56.0]

    def test_default_timeout_is_none(self) -> None:
        spy = _SpyRunner()
        run_nse_vulnerability_scan(
            spy,
            "10.0.0.1",
            [PortInfo(port=22)],
            version_intensity=2,
            scripts=("vulners",),
            min_cvss=0.0,
        )
        assert spy.timeouts == [None]
