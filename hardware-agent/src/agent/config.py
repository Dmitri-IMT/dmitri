"""Configuration for the hardware agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SCAN_MODES: tuple[str, ...] = ("quick", "standard", "extensive", "nspi", "max")


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


def port_stage_scripts(scan_mode: str) -> str:
    """Return the --script CSV for the port-scan stage (quick/standard only)."""
    if scan_mode == "nspi":
        return ",".join(NSPI_NSE_SCRIPTS)
    if scan_mode == "standard":
        return ",".join(STANDARD_NSE_SCRIPTS)
    return "vulners"


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
        "nspi": 1200.0,
        "max": 3600.0,
    },
}


def subprocess_timeout_for(scan_mode: str, stage: str) -> float:
    by_mode = TIMEOUTS.get(stage, TIMEOUTS["discovery"])
    return by_mode.get(scan_mode, by_mode["quick"])
