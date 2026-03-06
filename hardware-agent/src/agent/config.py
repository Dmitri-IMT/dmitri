"""Configuration scaffolding for the hardware agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentSettings:
    """Static defaults; will be replaced by env-driven configuration later."""

    backend_base_url: str = "https://backend.local/api/v1"
    scan_subnet: str = "192.168.0.0/24"
    scan_mode: str = "quick"  # Allowed values: quick, full
    device_id: str = "pi-agent-placeholder"


def load_settings() -> AgentSettings:
    """Return default settings (actual parsing deferred to Phase 2)."""

    return AgentSettings()
