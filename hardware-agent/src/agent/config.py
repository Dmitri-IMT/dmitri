"""Configuration loading for the hardware agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class AgentSettings:
    """Runtime configuration for the scanning agent."""

    scan_subnet: str | None = None
    scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"] = "quick"
    device_id: str = "pi-agent-placeholder"
    nmap_path: str | None = None
    min_cvss: float = 5.0
    max_workers: int = 4
    host_batch_size: int = 8
    output_path: str = str(Path("hardware-agent") / "artifacts" / "latest-scan.json")
    version_intensity: int = 5

    def with_overrides(
        self,
        *,
        scan_subnet: str | None = None,
        scan_mode: (
            Literal["quick", "standard", "extensive", "nspi", "max"] | None
        ) = None,
        output_path: str | None = None,
    ) -> AgentSettings:
        """Return a copy with CLI-provided overrides applied."""

        return replace(
            self,
            scan_subnet=scan_subnet or self.scan_subnet,
            scan_mode=scan_mode or self.scan_mode,
            output_path=output_path or self.output_path,
        )


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


def _parse_scan_mode(value: str | None) -> Literal["quick", "standard"]:
    normalized = (value or "quick").strip().lower()
    if normalized not in {"quick", "standard"}:
        raise ValueError("AGENT_SCAN_MODE must be 'quick' or 'standard'.")
    return normalized  # type: ignore[return-value]


def load_settings() -> AgentSettings:
    """Load settings from environment variables with sane defaults."""

    scan_mode = _parse_scan_mode(os.getenv("AGENT_SCAN_MODE"))
    return AgentSettings(
        scan_subnet=os.getenv("AGENT_SCAN_SUBNET"),
        scan_mode=scan_mode,
        device_id=os.getenv("AGENT_DEVICE_ID", "pi-agent-placeholder"),
        nmap_path=os.getenv("AGENT_NMAP_PATH"),
        min_cvss=float(os.getenv("AGENT_MIN_CVSS", "5.0")),
        max_workers=max(1, int(os.getenv("AGENT_MAX_WORKERS", "4"))),
        host_batch_size=max(1, int(os.getenv("AGENT_HOST_BATCH_SIZE", "8"))),
        output_path=os.getenv(
            "AGENT_OUTPUT_PATH",
            str(Path("hardware-agent") / "artifacts" / "latest-scan.json"),
        ),
        version_intensity=5,
    )
