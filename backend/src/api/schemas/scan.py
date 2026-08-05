from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, constr

SubnetCIDR = constr(
    pattern=r"^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$",
    strip_whitespace=True,
)


ScanMode = Literal["quick", "standard", "extensive", "nspi", "max"]


class PortPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    state: Literal["open", "closed", "filtered"]
    service: constr(min_length=1)
    version: str | None = None
    cpes: list[constr(min_length=1)] = Field(default_factory=list)


class HostPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    ports: list[PortPayload]


class FindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    protocol: Literal["tcp", "udp"] | None = None
    service: str | None = None
    source: str | None = None
    source_script: str | None = None
    cve_id: constr(pattern=r"^CVE-[0-9]{4}-[0-9]{4,}$") | None = None
    cvss_score: Annotated[float | None, Field(default=None, ge=0, le=10)]
    severity: Literal["low", "medium", "high", "critical"]
    title: constr(min_length=3)
    description: constr(min_length=3)
    recommendation: constr(min_length=3)
    evidence: constr(min_length=3)
    references: list[constr(min_length=1)] = Field(default_factory=list)


class ScanIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: ScanMode
    hosts: list[HostPayload]
    findings: list[FindingPayload]
    metadata: dict[str, str | int | float | bool] | None = None


class ScanIngestAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    scan_id: UUID
    hosts_received: Annotated[int, Field(ge=0)]
    status: Literal["accepted"]
