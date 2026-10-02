"""Structured in-memory models for Nmap scan stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from agent.ot.modbus.models import ModbusService

if TYPE_CHECKING:
    from agent.targeted.models import TargetedUnitResult


@dataclass(slots=True)
class OperatingSystemInfo:
    """Best operating-system fingerprint reported for a host."""

    name: str
    accuracy: int
    vendor: str | None = None
    family: str | None = None
    generation: str | None = None
    device_type: str | None = None
    cpes: list[str] = field(default_factory=list)


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
    tunnel: str | None = None
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


@dataclass(frozen=True, slots=True)
class MacIdentity:
    """One Nmap MAC observation: the address and the vendor paired with it."""

    mac: str | None = None
    vendor: str = "unknown"

    def merged_with(self, incoming: MacIdentity) -> MacIdentity:
        """Fold in a later observation; a vendor never follows a new MAC."""

        if incoming.mac is None:
            return self
        if incoming.mac == self.mac and incoming.vendor.casefold() == "unknown":
            return self
        return incoming


@dataclass(slots=True)
class PortScanResult:
    """Host identity, port inventory, and OS evidence from one Nmap host node."""

    ports: list[PortInfo] = field(default_factory=list)
    operating_system: OperatingSystemInfo | None = None
    identity: MacIdentity = MacIdentity()
    skipped: bool = False


CoverageStage = Literal[
    "ports", "deep_inspection", "ot_inspection", "targeted_assessment"
]
CoverageOutcome = Literal["completed", "partial", "failed", "timed_out", "skipped"]
StageEvidenceSource = Literal[
    "nmap_ports",
    "nmap_nse",
    "service_recovery",
    "port_discovery",
    "modbus_inspection",
    "not_run",
]


@dataclass(frozen=True, slots=True)
class StageCoverage:
    stage: CoverageStage
    outcome: CoverageOutcome
    evidence_source: StageEvidenceSource
    reason_code: str | None = None


@dataclass(slots=True)
class HostInfo:
    """Discovered host enriched across the full scan pipeline."""

    ip: str
    hostname: str
    identity: MacIdentity = MacIdentity()
    state: str = "up"
    ports: list[PortInfo] = field(default_factory=list)
    operating_system: OperatingSystemInfo | None = None
    host_scripts: list[ScriptResult] = field(default_factory=list)
    industrial_services: list[ModbusService] = field(default_factory=list)
    targeted_results: list[TargetedUnitResult] = field(default_factory=list)
    stage_coverage: list[StageCoverage] = field(default_factory=list)

    @property
    def open_ports(self) -> list[PortInfo]:
        """Return only ports that should feed service and NSE stages."""

        return [port for port in self.ports if port.state == "open"]
