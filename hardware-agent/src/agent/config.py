"""Configuration loading for the hardware agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

ScanMode = Literal["quick", "standard", "extensive", "nspi", "max"]


@dataclass(slots=True)
class AgentSettings:
    """Runtime configuration for the scanning agent."""

    scan_subnet: str | None = None
    scan_mode: ScanMode = "quick"
    device_id: str = "pi-agent-placeholder"
    nmap_path: str | None = None
    min_cvss: float = 5.0
    max_workers: int = 4
    host_batch_size: int = 8
    output_path: str = str(Path("hardware-agent") / "artifacts" / "latest-scan.json")
    version_intensity: int = 5
    web_tools_enabled: bool | None = None
    web_directory_enum_enabled: bool = True
    nikto_enabled: bool = True
    web_tool_timeout_seconds: int = 120
    web_tools_max_workers: int = 1
    web_wordlist_path: str | None = None
    testssl_enabled: bool = True
    testssl_path: str | None = None
    testssl_timeout_seconds: int = 180
    enum4linux_enabled: bool = True
    enum4linux_path: str | None = None
    enum4linux_timeout_seconds: int = 90

    def with_overrides(
        self,
        *,
        scan_subnet: str | None = None,
        scan_mode: ScanMode | None = None,
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


def _parse_scan_mode(value: str | None) -> ScanMode:
    normalized = (value or "quick").strip().lower()
    allowed = {"quick", "standard", "extensive", "nspi", "max"}
    if normalized not in allowed:
        raise ValueError(
            "AGENT_SCAN_MODE must be one of: quick, standard, extensive, nspi, max."
        )
    return normalized  # type: ignore[return-value]


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean environment value: {value!r}")


def _parse_bool(value: str | None, *, default: bool) -> bool:
    parsed = _parse_optional_bool(value)
    return default if parsed is None else parsed


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
        web_tools_enabled=_parse_optional_bool(os.getenv("AGENT_WEB_TOOLS_ENABLED")),
        web_directory_enum_enabled=_parse_bool(
            os.getenv("AGENT_WEB_DIRECTORY_ENUM_ENABLED"),
            default=True,
        ),
        nikto_enabled=_parse_bool(os.getenv("AGENT_NIKTO_ENABLED"), default=True),
        web_tool_timeout_seconds=max(
            1,
            int(os.getenv("AGENT_WEB_TOOL_TIMEOUT_SECONDS", "120")),
        ),
        web_tools_max_workers=max(
            1,
            int(os.getenv("AGENT_WEB_TOOLS_MAX_WORKERS", "1")),
        ),
        web_wordlist_path=os.getenv("AGENT_WEB_WORDLIST_PATH"),
        testssl_enabled=_parse_bool(
            os.getenv("AGENT_TESTSSL_ENABLED"),
            default=True,
        ),
        testssl_path=os.getenv("AGENT_TESTSSL_PATH"),
        testssl_timeout_seconds=max(
            1,
            int(os.getenv("AGENT_TESTSSL_TIMEOUT_SECONDS", "180")),
        ),
        enum4linux_enabled=_parse_bool(
            os.getenv("AGENT_ENUM4LINUX_ENABLED"),
            default=True,
        ),
        enum4linux_path=os.getenv("AGENT_ENUM4LINUX_PATH"),
        enum4linux_timeout_seconds=max(
            1,
            int(os.getenv("AGENT_ENUM4LINUX_TIMEOUT_SECONDS", "90")),
        ),
    )
