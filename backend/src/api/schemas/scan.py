from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress, constr

SubnetCIDR = constr(
    pattern=r"^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$",
    strip_whitespace=True,
)


ArtifactKind = Literal["nmap_xml", "nse_output"]
ScanProfile = Literal["single-host", "lab", "lan", "deep"]
TargetMode = Literal["single_host", "subnet", "multi_host"]


class Artifact(BaseModel):
    kind: ArtifactKind
    path: constr(min_length=1)
    stage: constr(min_length=1)
    host_ip: IPvAnyAddress | None = None


class Port(BaseModel):
    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    state: Literal["open", "closed", "filtered"]
    service: constr(min_length=1)
    version: str | None = None
    cpes: list[constr(min_length=1)] = Field(default_factory=list)


class Device(BaseModel):
    ip: IPvAnyAddress
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None = None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    ports: list[Port] = Field(default_factory=list)


class Finding(BaseModel):
    ip: IPvAnyAddress | None = None
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


class ScanResult(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    target_mode: TargetMode
    scan_profile: ScanProfile
    devices: list[Device] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None


class ScanIngestResponse(BaseModel):
    message: str
    scan_id: UUID
    devices_received: int
