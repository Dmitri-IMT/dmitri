"""Unit tests for NSPI_NSE_SCRIPTS and NSPI_PORTS constants."""

from __future__ import annotations

from agent.config import (
    NSPI_HOST_TIMEOUT,
    NSPI_NSE_SCRIPTS,
    NSPI_PORTS,
    NSPI_SCRIPT_TIMEOUT,
)
from agent.discovery.port_discovery import NSPI_PASS1_ARGS, NSPI_PASS2_ARGS
from agent.discovery.vulnerability_detection import run_nse_vulnerability_scan
from agent.scanner.models import PortInfo

EXPECTED_SCRIPTS = (
    "modbus-discover",
    "enip-info",
    "smb-protocols",
    "smb2-security-mode",
    "smb-security-mode",
    "smb-vuln-ms17-010",
    "smb-enum-shares",
    "rdp-enum-encryption",
    "ssh-auth-methods",
    "ssh2-enum-algos",
    "ssl-cert",
    "ssl-enum-ciphers",
    "http-title",
    "vulners",
)

EXPECTED_PORTS = {"502", "4840", "44818", "445", "139", "3389", "5985"}


class TestNspiNseScripts:
    def test_contains_exactly_14_scripts(self) -> None:
        assert len(NSPI_NSE_SCRIPTS) == 14

    def test_matches_expected_scripts(self) -> None:
        assert NSPI_NSE_SCRIPTS == EXPECTED_SCRIPTS

    def test_bacnet_info_excluded(self) -> None:
        assert "bacnet-info" not in NSPI_NSE_SCRIPTS

    def test_s7_info_excluded(self) -> None:
        assert "s7-info" not in NSPI_NSE_SCRIPTS

    def test_generated_nse_argv_keeps_exact_script_tuple(self) -> None:
        class CapturingRunner:
            nmap_path = "nmap"

            def __init__(self) -> None:
                self.arguments = None

            def run_xml(self, arguments, *, timeout=None):
                import xml.etree.ElementTree as ET

                self.arguments = arguments
                return ET.fromstring("<nmaprun><host /></nmaprun>")

        runner = CapturingRunner()
        run_nse_vulnerability_scan(
            runner,
            "192.168.10.30",
            [PortInfo(port=502)],
            version_intensity=5,
            scripts=NSPI_NSE_SCRIPTS,
            min_cvss=5.0,
        )

        assert runner.arguments is not None
        script_index = runner.arguments.index("--script")
        assert runner.arguments[script_index + 1] == ",".join(EXPECTED_SCRIPTS)

    def test_generated_nse_argv_has_internal_timeouts_and_os_detection(self) -> None:
        class CapturingRunner:
            nmap_path = "nmap"

            def __init__(self) -> None:
                self.arguments = None

            def run_xml(self, arguments, *, timeout=None):
                import xml.etree.ElementTree as ET

                self.arguments = arguments
                return ET.fromstring("<nmaprun><host /></nmaprun>")

        runner = CapturingRunner()
        run_nse_vulnerability_scan(
            runner,
            "192.168.10.30",
            [PortInfo(port=502)],
            version_intensity=5,
            scripts=NSPI_NSE_SCRIPTS,
            min_cvss=5.0,
            script_timeout=NSPI_SCRIPT_TIMEOUT,
            host_timeout=NSPI_HOST_TIMEOUT,
            detect_os=True,
        )

        assert runner.arguments is not None
        assert "-O" in runner.arguments
        script_timeout_index = runner.arguments.index("--script-timeout")
        assert runner.arguments[script_timeout_index + 1] == NSPI_SCRIPT_TIMEOUT
        host_timeout_index = runner.arguments.index("--host-timeout")
        assert runner.arguments[host_timeout_index + 1] == NSPI_HOST_TIMEOUT


class TestNspiPorts:
    def test_contains_all_7_ot_ports(self) -> None:
        ports = set(NSPI_PORTS.split(","))
        assert ports == EXPECTED_PORTS

    def test_bacnet_port_excluded(self) -> None:
        assert "47808" not in NSPI_PORTS.split(",")

    def test_s7_port_excluded(self) -> None:
        assert "102" not in NSPI_PORTS.split(",")

    def test_both_port_passes_defer_service_and_script_enrichment(self) -> None:
        for arguments in (NSPI_PASS1_ARGS, NSPI_PASS2_ARGS):
            assert "-sV" not in arguments
            assert "--script" not in arguments

    def test_internal_host_timeout_is_preserved(self) -> None:
        for arguments in (NSPI_PASS1_ARGS, NSPI_PASS2_ARGS):
            timeout_index = arguments.index("--host-timeout")
            assert arguments[timeout_index + 1] == NSPI_HOST_TIMEOUT
