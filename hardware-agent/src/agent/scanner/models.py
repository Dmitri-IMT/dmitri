"""Structured in-memory models for Nmap scan stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.ot.modbus.models import ModbusService


@dataclass(slots=True)
class ScriptResult:
    """Structured representation of an NSE script execution."""

    script_id: str
    output: str = ""
    data: Any = None
    is_host_script: bool = False


@dataclass(slots=True)
class ServiceInfo:
    """Detected service fingerprint for a given port."""

    name: str = ""
    product: str = ""
    version: str = ""
    extra_info: str = ""
    cpes: list[str] = field(default_factory=list)

    @property
    def banner(self) -> str | None:
        """Return a compact string suitable for the shared contract."""

        parts = [self.product.strip(), self.version.strip(), self.extra_info.strip()]
        normalized = " ".join(part for part in parts if part)
        return normalized or None


@dataclass(slots=True)
class PortInfo:
    """State and enrichment data for a port on a host."""

    port: int
    protocol: str = "tcp"
    state: str = "open"
    service: ServiceInfo = field(default_factory=ServiceInfo)
    scripts: list[ScriptResult] = field(default_factory=list)


@dataclass(slots=True)
class HostInfo:
    """Discovered host enriched across the full scan pipeline."""

    ip: str
    hostname: str
    mac: str | None = None
    vendor: str = "unknown"
    state: str = "up"
    ports: list[PortInfo] = field(default_factory=list)
    host_scripts: list[ScriptResult] = field(default_factory=list)
    industrial_services: list[ModbusService] = field(default_factory=list)

    @property
    def open_ports(self) -> list[PortInfo]:
        """Return only ports that should feed service and NSE stages."""

        return [port for port in self.ports if port.state == "open"]
