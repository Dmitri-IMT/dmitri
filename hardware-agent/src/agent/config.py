"""Configuration for the hardware agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent.scanner.errors import UnsupportedScanDepth

SCAN_MODES: tuple[str, ...] = ("quick", "standard", "extensive", "nspi", "max")
TARGETED_MODES: tuple[str, ...] = ("extensive", "max", "nspi")
NSPI_SUBMODES: tuple[str, ...] = (
    "inventory",
    "read_only_mapping",
    "active_validation",
)
NspiSubmode = Literal["inventory", "read_only_mapping", "active_validation"]

TARGETED_STAGE_TIMEOUT_S: dict[str, float] = {
    "extensive": 1800.0,
    "max": 3600.0,
    "nspi": 1800.0,
}
TARGETED_UNIT_TIMEOUT_S: dict[str, float] = {
    "ffuf": 480.0,
    "nikto": 800.0,
    "testssl.sh": 300.0,
    "enum4linux-ng": 180.0,
    "ssh-audit": 60.0,
    "ftp-check": 15.0,
    "telnet-check": 10.0,
}
TARGETED_MAX_UNITS = 96
TARGETED_STDIO_LIMIT_BYTES = 131_072
TARGETED_REPORT_LIMIT_BYTES = 2_097_152
TARGETED_EVIDENCE_LIMIT_CHARS = 4_096
TARGETED_DIAGNOSTIC_LIMIT_CHARS = 512
TARGETED_MAX_ISSUES_PER_UNIT = 128
TARGETED_WEB_MAX_VALIDATIONS_PER_UNIT = 32
TARGETED_COVERAGE_LIMIT_CHARS = 2_048
TARGETED_WORDLIST_MAX_BYTES = 1_048_576
TARGETED_WORDLIST_MAX_ENTRIES = 10_000


@dataclass(slots=True)
class AgentSettings:
    """Runtime configuration for the scanning agent."""

    scan_subnet: str | None = None
    scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"] = "quick"
    nmap_path: str | None = None
    min_cvss: float = 5.0
    max_workers: int = 4
    host_batch_size: int = 8
    version_intensity: int = 5
    scan_deadline_s: int = 0
    unit_failure_threshold: float = 0.5
    transient_retries: int = 1
    nspi_submode: NspiSubmode = "inventory"


STANDARD_NSE_SCRIPTS = (
    "vulners",
    "smb-protocols",
    "smb2-security-mode",
    "ssh-auth-methods",
    "http-title",
    "http-server-header",
)

QUICK_NSE_SCRIPTS = ("vulners",)

EXTENSIVE_NSE_SCRIPTS = (
    "vulners",
    "smb-protocols",
    "smb2-security-mode",
    "ssh-auth-methods",
    "http-title",
    "http-server-header",
    "ssl-cert",
    "ssl-enum-ciphers",
    "http-methods",
    "ftp-anon",
    "banner",
)

NSPI_PORTS = "502,4840,44818,445,139,3389,5985"
NSPI_SCRIPT_TIMEOUT = "60s"
NSPI_HOST_TIMEOUT = "300s"

NSPI_NSE_SCRIPTS = (
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


def deep_stage_scripts(scan_mode: str) -> tuple[str, ...]:
    """Return the script tuple for the deep-inspection stage."""
    if scan_mode == "nspi":
        return NSPI_NSE_SCRIPTS
    if scan_mode == "standard":
        return STANDARD_NSE_SCRIPTS
    if scan_mode == "extensive":
        return EXTENSIVE_NSE_SCRIPTS
    if scan_mode == "max":
        return EXTENSIVE_NSE_SCRIPTS
    return QUICK_NSE_SCRIPTS


def effective_version_intensity(configured: int) -> int:
    """Keep the authoritative service probe at least as deep as Nmap's default."""
    return max(configured, 7)


def min_cvss_for_mode(scan_mode: str) -> float:
    if scan_mode == "extensive":
        return 3.0
    if scan_mode == "max":
        return 1.0
    return 5.0


TIMEOUTS: dict[str, dict[str, float]] = {
    "discovery": {
        "quick": 600.0,
        "standard": 600.0,
        "extensive": 600.0,
        "nspi": 600.0,
        "max": 600.0,
    },
    "ports": {
        "quick": 600.0,
        "standard": 900.0,
        "extensive": 1800.0,
        "nspi": 600.0,
        "max": 3600.0,
    },
    "nse": {
        "quick": 900.0,
        "standard": 1200.0,
        "extensive": 2400.0,
        "nspi": 600.0,
        "max": 3600.0,
    },
}


def subprocess_timeout_for(scan_mode: str, stage: str) -> float:
    by_mode = TIMEOUTS.get(stage, TIMEOUTS["discovery"])
    return by_mode.get(scan_mode, by_mode["quick"])


def validate_nspi_depth(scan_mode: str, nspi_submode: NspiSubmode) -> None:
    """Refuse unpermitted NSPi depth before any active request."""
    if scan_mode != "nspi":
        if nspi_submode != "inventory":
            raise UnsupportedScanDepth(nspi_submode)
        return
    if nspi_submode not in NSPI_SUBMODES:
        raise UnsupportedScanDepth(nspi_submode)
    if nspi_submode == "active_validation":
        raise UnsupportedScanDepth("active_validation")
