from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress, constr

SubnetCIDR = constr(
    pattern=r"^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$",
    strip_whitespace=True,
)


class Port(BaseModel):
    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    state: Literal["open", "closed", "filtered"]
    service: constr(min_length=1)
    version: str | None = None


class Device(BaseModel):
    ip: IPvAnyAddress
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    ports: list[Port] = Field(default_factory=list)


class Finding(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    title: constr(min_length=3)
    description: constr(min_length=3)
    recommendation: constr(min_length=3)
    evidence: constr(min_length=3)


class ScanResult(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: Literal["quick", "full"]
    devices: list[Device] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None


class ScanIngestResponse(BaseModel):
    message: str
    scan_id: UUID
    devices_received: int
