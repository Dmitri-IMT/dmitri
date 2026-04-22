"""Configuration loading for the hardware agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

DEFAULT_NSE_SCRIPTS = (
    "vulners",
    "smb2-security-mode",
    "smb-protocols",
    "ssh-auth-methods",
    "ssh2-enum-algos",
    "http-title",
    "http-server-header",
    "http-methods",
    "ssl-cert",
)


@dataclass(slots=True)
class AgentSettings:
    """Runtime configuration for the scanning agent."""

    backend_base_url: str = "https://backend.local/api/v1"
    submit_results: bool = False
    scan_subnet: str | None = None
    scan_mode: Literal["quick", "full"] = "quick"
    device_id: str = "pi-agent-placeholder"
    nmap_path: str | None = None
    nmap_scripts: tuple[str, ...] = DEFAULT_NSE_SCRIPTS
    min_cvss: float = 5.0
    max_workers: int = 4
    host_batch_size: int = 8
    output_path: str = str(Path("hardware-agent") / "artifacts" / "latest-scan.json")
    version_intensity: int = 5

    def with_overrides(
        self,
        *,
        scan_subnet: str | None = None,
        scan_mode: Literal["quick", "full"] | None = None,
        output_path: str | None = None,
    ) -> AgentSettings:
        """Return a copy with CLI-provided overrides applied."""

        return replace(
            self,
            scan_subnet=scan_subnet or self.scan_subnet,
            scan_mode=scan_mode or self.scan_mode,
            output_path=output_path or self.output_path,
        )


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_NSE_SCRIPTS
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or DEFAULT_NSE_SCRIPTS


def _parse_scan_mode(value: str | None) -> Literal["quick", "full"]:
    normalized = (value or "quick").strip().lower()
    if normalized not in {"quick", "full"}:
        raise ValueError("AGENT_SCAN_MODE must be either 'quick' or 'full'.")
    return normalized  # type: ignore[return-value]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> AgentSettings:
    """Load settings from environment variables with sane defaults."""

    scan_mode = _parse_scan_mode(os.getenv("AGENT_SCAN_MODE"))
    return AgentSettings(
        backend_base_url=os.getenv("AGENT_BACKEND_BASE_URL", "https://backend.local/api/v1"),
        submit_results=_parse_bool(os.getenv("AGENT_SUBMIT_RESULTS"), default=False),
        scan_subnet=os.getenv("AGENT_SCAN_SUBNET"),
        scan_mode=scan_mode,
        device_id=os.getenv("AGENT_DEVICE_ID", "pi-agent-placeholder"),
        nmap_path=os.getenv("AGENT_NMAP_PATH"),
        nmap_scripts=_parse_csv(os.getenv("AGENT_NMAP_SCRIPTS")),
        min_cvss=float(os.getenv("AGENT_MIN_CVSS", "5.0")),
        max_workers=max(1, int(os.getenv("AGENT_MAX_WORKERS", "4"))),
        host_batch_size=max(1, int(os.getenv("AGENT_HOST_BATCH_SIZE", "8"))),
        output_path=os.getenv(
            "AGENT_OUTPUT_PATH",
            str(Path("hardware-agent") / "artifacts" / "latest-scan.json"),
        ),
        version_intensity=7 if scan_mode == "full" else 5,
    )
