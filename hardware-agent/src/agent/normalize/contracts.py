"""Pydantic payload models matching the shared contracts."""

from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, constr

from agent.ot.untrusted import (
    MAX_ADDRESS_RANGES_PER_UNIT,
    MAX_DEVICE_STRING_CHARS,
    MAX_IDENTIFICATION_OBJECTS,
    MAX_IDENTIFICATION_SOURCES,
)

DeviceString = Annotated[str | None, Field(max_length=MAX_DEVICE_STRING_CHARS)]
ValueDigest = Annotated[
    str | None,
    Field(pattern=r"^hmac-sha256:[0-9a-f]{64}$"),
]

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
    cpes: list[constr(min_length=1)] = Field(default_factory=list)


class OperatingSystemDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: constr(min_length=1)
    accuracy: Annotated[int, Field(ge=0, le=100, strict=True)]
    vendor: str | None = None
    family: str | None = None
    generation: str | None = None
    device_type: str | None = None
    cpes: list[constr(min_length=1)] = Field(default_factory=list)


class ModbusDeviceIdentificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: DeviceString = None
    product_code: DeviceString = None
    major_minor_revision: DeviceString = None
    vendor_url: DeviceString = None
    product_name: DeviceString = None
    model_name: DeviceString = None
    user_application_name: DeviceString = None
    objects: dict[str, str] = Field(
        default_factory=dict, max_length=MAX_IDENTIFICATION_OBJECTS
    )
    truncated: bool = False


class ModbusAddressRangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address_space: Literal[
        "coil", "discrete_input", "holding_register", "input_register"
    ]
    start_address: Annotated[int, Field(ge=0, le=65535)]
    count: Annotated[int, Field(ge=1, le=65536)]
    status: Literal[
        "readable",
        "illegal_address",
        "illegal_function",
        "timeout",
        "error",
        "skipped",
    ]
    exception_code: Annotated[int | None, Field(default=None, ge=1, le=255)]
    label: DeviceString = None
    value_digest: ValueDigest = None
    observed_at: datetime


class ModbusUnitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: Annotated[int, Field(ge=0, le=255)]
    status: Literal["responding", "exception", "timeout", "error", "skipped"]
    exception_code: Annotated[int | None, Field(default=None, ge=1, le=255)]
    error: DeviceString = None
    device_identification: ModbusDeviceIdentificationPayload | None = None
    identification_sources: list[constr(min_length=1)] = Field(
        default_factory=list, max_length=MAX_IDENTIFICATION_SOURCES
    )
    address_ranges: list[ModbusAddressRangePayload] = Field(
        default_factory=list, max_length=MAX_ADDRESS_RANGES_PER_UNIT
    )


class ModbusTcpServicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["modbus_tcp"] = "modbus_tcp"
    port: Annotated[int, Field(ge=1, le=65535)]
    confidence: Literal["suspected", "confirmed"]
    evidence_sources: list[constr(min_length=1)] = Field(default_factory=list)
    mapping_source: str | None = None
    write_requests_sent: Annotated[int, Field(default=0, ge=0)]
    units: list[ModbusUnitPayload] = Field(default_factory=list)


class HostPayload(BaseModel):
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None = None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    operating_system: OperatingSystemDetection | None = None
    ports: list[PortPayload] = Field(default_factory=list)
    industrial_services: list[ModbusTcpServicePayload] = Field(default_factory=list)


class FindingPayload(BaseModel):
    ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    unit_id: Annotated[int | None, Field(default=None, ge=0, le=255)] = None
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
    scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"]
    hosts: list[HostPayload] = Field(default_factory=list)
    findings: list[FindingPayload] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None
