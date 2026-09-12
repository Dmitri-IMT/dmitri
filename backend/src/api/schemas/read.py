from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, constr

from api.core.error_codes import ScanErrorCode
from api.core.machine_type import MachineType
from api.core.severity import Severity

from .industrial import (
    ModbusAddressRangePayload,
    ModbusDeviceIdentificationPayload,
)
from .operating_system import OperatingSystemDetection

ScanMode = Literal["quick", "standard", "extensive", "nspi", "max"]
ScanStatus = Literal["pending", "accepted", "processing", "completed", "failed"]
ScanSortBy = Literal["timestamp", "status", "scan_mode"]
HostSortBy = Literal[
    "last_seen_at", "hostname", "vendor", "ip", "vulnerability_count"
]
HostGroup = Literal["active", "quiet"]
SortOrder = Literal["asc", "desc"]


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    state: Literal["open", "closed", "filtered"]
    service: constr(min_length=1)
    version: str | None = None


class HostPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    service: constr(min_length=1)
    version: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime


class ModbusDeviceIdentificationView(ModbusDeviceIdentificationPayload):
    pass


class ModbusAddressRangeView(ModbusAddressRangePayload):
    pass


class ModbusUnitView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[int, Field(ge=1)]
    unit_id: Annotated[int, Field(ge=0, le=255)]
    status: Literal[
        "responding", "exception", "timeout", "error", "skipped"
    ]
    exception_code: Annotated[int | None, Field(default=None, ge=1, le=255)]
    error: str | None = None
    identification: ModbusDeviceIdentificationView | None = None
    identification_sources: list[constr(min_length=1)] = Field(
        default_factory=list
    )
    address_ranges: list[ModbusAddressRangeView] = Field(default_factory=list)


class IndustrialServiceView(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "description": (
                "Industrial observations are retained for "
                "INDUSTRIAL_OBSERVATION_RETENTION_DAYS (180) days from scan "
                "ingestion. No pruning job enforces that period yet."
            )
        },
    )

    protocol: Literal["modbus_tcp"]
    port: Annotated[int, Field(ge=1, le=65535)]
    confidence: Literal["suspected", "confirmed"]
    mapping_source: str | None = None
    evidence_sources: list[constr(min_length=1)] = Field(default_factory=list)
    units: list[ModbusUnitView] = Field(default_factory=list)


class ScanHostView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host_id: UUID
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    operating_system: OperatingSystemDetection | None = None
    ports: list[Port]
    industrial_services: list[IndustrialServiceView] = Field(
        default_factory=list
    )
    unreadable_fields: list[str] = Field(default_factory=list)


class FindingModbusUnitRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[int, Field(ge=1)]
    unit_id: Annotated[int, Field(ge=0, le=255)]
    port: Annotated[int, Field(ge=1, le=65535)]


class FindingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    scan_id: UUID
    host_id: UUID | None = None
    host_ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    protocol: Literal["tcp", "udp"] | None = None
    service: str | None = None
    source: str | None = None
    source_script: str | None = None
    cve_id: constr(pattern=r"^CVE-[0-9]{4}-[0-9]{4,}$") | None = None
    cvss_score: Annotated[float | None, Field(default=None, ge=0, le=10)]
    severity: Severity
    title: constr(min_length=3)
    description: constr(min_length=3)
    recommendation: constr(min_length=3)
    evidence: constr(min_length=3)
    references: list[constr(min_length=1)] = Field(default_factory=list)
    modbus_unit: FindingModbusUnitRef | None = None
    detected_at: datetime
    risk_score: Annotated[float | None, Field(default=None, ge=0, le=100)]
    exploitability: Annotated[float | None, Field(default=None, ge=0, le=1)]
    confidence: Literal["tentative", "probable", "confirmed"] | None = None
    risk_rationale: str | None = None
    host_hostname: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    fixed_at: datetime | None = None


class HostSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host_id: UUID
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None
    hostname: str
    vendor: str
    operating_system: OperatingSystemDetection | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    open_ports_count: Annotated[int, Field(ge=0)]
    machine_type: MachineType
    vulnerability_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None = None
    unreadable_fields: list[str] = Field(default_factory=list)


class HostScanHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    scan_mode: ScanMode
    operating_system: OperatingSystemDetection | None = None
    open_ports_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None = None


class HostDetailResponse(HostSummary):
    ports: list[HostPort]
    industrial_services: list[IndustrialServiceView] = Field(
        default_factory=list
    )
    scan_history: list[HostScanHistoryEntry]


class ScanDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    subnet: constr(pattern=r"^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$")
    scan_mode: ScanMode
    hosts: list[ScanHostView]
    findings: list[FindingRead]
    metadata: dict[str, str | int | float | bool] | None = None
    status: ScanStatus
    command_id: UUID | None = None
    error_code: ScanErrorCode | None = None
    host_count: Annotated[int, Field(ge=0)]
    finding_count: Annotated[int, Field(ge=0)]
    agent_id: UUID | None = None
    box_name: str | None = None
    duration: Annotated[int | None, Field(default=None, ge=0)] = None


class ScanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    subnet: str
    scan_mode: ScanMode
    status: ScanStatus
    host_count: Annotated[int, Field(ge=0)]
    finding_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None = None
    agent_id: UUID | None = None
    box_name: str | None = None
    duration: Annotated[int | None, Field(default=None, ge=0)] = None


class ScanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ScanSummary]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class HostListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[HostSummary]
    total: Annotated[int, Field(ge=0)]
    quiet_total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class FindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[FindingRead]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class SeverityBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical: Annotated[int, Field(ge=0)] = 0
    high: Annotated[int, Field(ge=0)] = 0
    medium: Annotated[int, Field(ge=0)] = 0
    low: Annotated[int, Field(ge=0)] = 0


class ScanRiskSummaryResponse(BaseModel):
    """Bounded, evidence-bearing scan context for UI and future LLM tools."""

    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    total_findings: Annotated[int, Field(ge=0)]
    scored_findings: Annotated[int, Field(ge=0)]
    confirmed_findings: Annotated[int, Field(ge=0)]
    kev_findings: Annotated[int, Field(ge=0)]
    average_risk_score: Annotated[
        float | None, Field(default=None, ge=0, le=100)
    ]
    max_risk_score: Annotated[float | None, Field(default=None, ge=0, le=100)]
    severity: SeverityBreakdown
    top_findings: list[FindingRead]
