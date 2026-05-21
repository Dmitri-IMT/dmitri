"""Unit tests for NSPI_NSE_SCRIPTS and NSPI_PORTS constants."""

from __future__ import annotations

from agent.config import NSPI_NSE_SCRIPTS, NSPI_PORTS

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


class TestNspiPorts:
    def test_contains_all_7_ot_ports(self) -> None:
        ports = set(NSPI_PORTS.split(","))
        assert ports == EXPECTED_PORTS

    def test_bacnet_port_excluded(self) -> None:
        assert "47808" not in NSPI_PORTS.split(",")

    def test_s7_port_excluded(self) -> None:
        assert "102" not in NSPI_PORTS.split(",")
