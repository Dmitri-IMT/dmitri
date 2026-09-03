"""Pydantic payload models matching the shared contracts."""

from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, constr

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


class ModbusDeviceIdentificationPayload(BaseModel):
    vendor_name: str | None = None
    product_code: str | None = None
    major_minor_revision: str | None = None
    vendor_url: str | None = None
    product_name: str | None = None
    model_name: str | None = None
    user_application_name: str | None = None
    objects: dict[str, str] = Field(default_factory=dict)


class ModbusAddressRangePayload(BaseModel):
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
    label: str | None = None
    nonzero_count: Annotated[int | None, Field(default=None, ge=0)]
    value_min: int | None = None
    value_max: int | None = None
    values: list[int | bool] | None = None
    value_sha256: str | None = None
    observed_at: datetime


class ModbusValidationPayload(BaseModel):
    address_space: Literal["coil", "holding_register"]
    address: Annotated[int, Field(ge=0, le=65535)]
    label: constr(min_length=1)
    function_code: Literal[5, 6]
    original_value: int | bool | None = None
    expected_current_value: int | bool
    test_value: int | bool
    write_status: Literal["accepted", "rejected", "timeout", "error", "skipped"]
    read_back_value: int | bool | None = None
    restoration_status: Literal["not_required", "verified", "unverified", "failed"]
    final_value: int | bool | None = None
    change_ticket: constr(min_length=1)
    started_at: datetime
    completed_at: datetime


class ModbusUnitPayload(BaseModel):
    unit_id: Annotated[int, Field(ge=0, le=255)]
    status: Literal["responding", "exception", "timeout", "error", "skipped"]
    exception_code: Annotated[int | None, Field(default=None, ge=1, le=255)]
    error: str | None = None
    device_identification: ModbusDeviceIdentificationPayload | None = None
    identification_sources: list[constr(min_length=1)] = Field(default_factory=list)
    address_ranges: list[ModbusAddressRangePayload] = Field(default_factory=list)
    validations: list[ModbusValidationPayload] = Field(default_factory=list)


class ModbusTcpServicePayload(BaseModel):
    protocol: Literal["modbus_tcp"] = "modbus_tcp"
    port: Annotated[int, Field(ge=1, le=65535)]
    confidence: Literal["suspected", "confirmed"]
    evidence_sources: list[constr(min_length=1)] = Field(default_factory=list)
    mapping_source: str | None = None
    units: list[ModbusUnitPayload] = Field(default_factory=list)


class HostPayload(BaseModel):
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None = None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    ports: list[PortPayload] = Field(default_factory=list)
    industrial_services: list[ModbusTcpServicePayload] = Field(default_factory=list)


class FindingPayload(BaseModel):
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


class ScanPayload(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"]
    hosts: list[HostPayload] = Field(default_factory=list)
    findings: list[FindingPayload] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None
