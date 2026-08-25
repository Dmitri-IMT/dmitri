from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, constr

from api.core.error_codes import ScanErrorCode
from api.core.severity import Severity

ScanMode = Literal["quick", "standard", "extensive", "nspi", "max"]
ScanStatus = Literal["pending", "accepted", "processing", "completed", "failed"]
ScanSortBy = Literal["timestamp", "status", "scan_mode"]
HostSortBy = Literal["last_seen_at", "hostname", "vendor", "ip"]
SortOrder = Literal["asc", "desc"]


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    state: Literal["open", "closed", "filtered"]
    service: constr(min_length=1)
    version: str | None = None


class ScanHostView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host_id: UUID
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    ports: list[Port]


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
    detected_at: datetime


class HostSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host_id: UUID
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None
    hostname: str
    vendor: str
    first_seen_at: datetime
    last_seen_at: datetime
    open_ports_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None = None


class HostScanHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    scan_mode: ScanMode
    open_ports_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None = None


class HostDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host_id: UUID
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None
    hostname: str
    vendor: str
    first_seen_at: datetime
    last_seen_at: datetime
    open_ports_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None = None
    ports: list[Port]
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


class ScanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ScanSummary]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class HostListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[HostSummary]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class FindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[FindingRead]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]
