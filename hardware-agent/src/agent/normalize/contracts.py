"""Pydantic payload models matching the shared contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress, constr

SubnetCIDR = constr(
    pattern=r"^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$",
    strip_whitespace=True,
)


class PortPayload(BaseModel):
    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    state: Literal["open", "closed", "filtered"]
    service: constr(min_length=1)
    version: str | None = None


class DevicePayload(BaseModel):
    ip: IPvAnyAddress
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None = None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    ports: list[PortPayload] = Field(default_factory=list)


class FindingPayload(BaseModel):
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


class ScanPayload(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: Literal["quick", "full"]
    devices: list[DevicePayload] = Field(default_factory=list)
    findings: list[FindingPayload] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None
