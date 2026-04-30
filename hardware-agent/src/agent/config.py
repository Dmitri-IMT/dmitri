"""Configuration loading for the hardware agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

ScanProfile = Literal["single-host", "lab", "lan", "deep"]
TargetMode = Literal["single_host", "subnet", "multi_host"]


@dataclass(slots=True)
class AgentSettings:
    """Runtime configuration for the scanning agent."""

    backend_base_url: str = "https://backend.local/api/v1"
    submit_results: bool = False
    scan_target: str | None = None
    scan_subnet: str | None = None
    scan_profile: ScanProfile = "lan"
    target_mode: TargetMode | None = None
    device_id: str = "pi-agent-placeholder"
    nmap_path: str | None = None
    vulners_script: str = "vulners"
    min_cvss: float = 5.0
    max_workers: int = 4
    host_batch_size: int = 8
    output_path: str = str(Path("hardware-agent") / "artifacts" / "latest-scan.json")
    save_raw_artifacts: bool = False
    raw_artifacts_dir: str = str(Path("hardware-agent") / "artifacts" / "raw")

    def with_overrides(
        self,
        *,
        scan_target: str | None = None,
        scan_subnet: str | None = None,
        scan_profile: ScanProfile | None = None,
        target_mode: TargetMode | None = None,
        output_path: str | None = None,
    ) -> AgentSettings:
        """Return a copy with CLI-provided overrides applied."""

        return replace(
            self,
            scan_target=scan_target or self.scan_target,
            scan_subnet=scan_subnet or self.scan_subnet,
            scan_profile=scan_profile or self.scan_profile,
            target_mode=target_mode or self.target_mode,
            output_path=output_path or self.output_path,
        )


def _parse_scan_profile(value: str | None) -> ScanProfile:
    normalized = (value or "lan").strip().lower()
    if normalized not in {"single-host", "lab", "lan", "deep"}:
        raise ValueError(
            "AGENT_SCAN_PROFILE must be one of 'single-host', 'lab', 'lan', or 'deep'."
        )
    return normalized  # type: ignore[return-value]


def _parse_target_mode(value: str | None) -> TargetMode | None:
    if value is None or not value.strip():
        return None

    normalized = value.strip().lower()
    if normalized not in {"single_host", "subnet", "multi_host"}:
        raise ValueError(
            "AGENT_TARGET_MODE must be one of 'single_host', 'subnet', or 'multi_host'."
        )
    return normalized  # type: ignore[return-value]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> AgentSettings:
    """Load settings from environment variables with sane defaults."""

    return AgentSettings(
        backend_base_url=os.getenv(
            "AGENT_BACKEND_BASE_URL", "https://backend.local/api/v1"
        ),
        submit_results=_parse_bool(os.getenv("AGENT_SUBMIT_RESULTS"), default=False),
        scan_target=os.getenv("AGENT_SCAN_TARGET"),
        scan_subnet=os.getenv("AGENT_SCAN_SUBNET"),
        scan_profile=_parse_scan_profile(os.getenv("AGENT_SCAN_PROFILE")),
        target_mode=_parse_target_mode(os.getenv("AGENT_TARGET_MODE")),
        device_id=os.getenv("AGENT_DEVICE_ID", "pi-agent-placeholder"),
        nmap_path=os.getenv("AGENT_NMAP_PATH"),
        vulners_script=os.getenv("AGENT_VULNERS_SCRIPT", "vulners"),
        min_cvss=float(os.getenv("AGENT_MIN_CVSS", "5.0")),
        max_workers=max(1, int(os.getenv("AGENT_MAX_WORKERS", "4"))),
        host_batch_size=max(1, int(os.getenv("AGENT_HOST_BATCH_SIZE", "8"))),
        output_path=os.getenv(
            "AGENT_OUTPUT_PATH",
            str(Path("hardware-agent") / "artifacts" / "latest-scan.json"),
        ),
        save_raw_artifacts=_parse_bool(
            os.getenv("AGENT_SAVE_RAW_ARTIFACTS"),
            default=False,
        ),
        raw_artifacts_dir=os.getenv(
            "AGENT_RAW_ARTIFACTS_DIR",
            str(Path("hardware-agent") / "artifacts" / "raw"),
        ),
    )
