"""Pydantic payload models matching the shared contracts."""

from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    constr,
    field_validator,
    model_validator,
)

from agent.assessment.policy import (
    MAX_ASSESSMENT_TEXT_CHARS,
    MAX_CONFLICTS,
    MAX_EVIDENCE_ITEMS,
    MAX_EVIDENCE_SOURCE_CHARS,
    MAX_EVIDENCE_VALUE_CHARS,
    MAX_LIMITATIONS,
    MAX_REASON_CHARS,
    AssessmentConfidence,
    EvidenceKind,
    ExposureAttention,
    ExposureConfidence,
    ExposureRole,
    MachineType,
)
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

AssessmentText = constr(
    min_length=1,
    max_length=MAX_ASSESSMENT_TEXT_CHARS,
    strip_whitespace=True,
)
AssessmentReason = constr(
    min_length=1,
    max_length=MAX_REASON_CHARS,
    strip_whitespace=True,
)


class AssessmentEvidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    source: constr(
        min_length=1,
        max_length=MAX_EVIDENCE_SOURCE_CHARS,
        strip_whitespace=True,
    )
    value: constr(
        min_length=1,
        max_length=MAX_EVIDENCE_VALUE_CHARS,
        strip_whitespace=True,
    )


def _ordered_evidence(
    items: list[AssessmentEvidencePayload],
) -> list[AssessmentEvidencePayload]:
    unique: dict[tuple[str, str, str], AssessmentEvidencePayload] = {}
    for item in items:
        key = (item.kind, item.source, item.value.casefold())
        unique.setdefault(key, item)
    return sorted(
        unique.values(),
        key=lambda item: (item.kind, item.source, item.value),
    )


class ExposurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip: IPv4Address
    port: Annotated[int, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    observed_service: AssessmentText
    observed_version: AssessmentText | None = None
    role: ExposureRole
    attention: ExposureAttention
    confidence: ExposureConfidence
    reason: AssessmentReason
    evidence: list[AssessmentEvidencePayload] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_ITEMS,
    )

    @field_validator("evidence")
    @classmethod
    def order_evidence(
        cls, value: list[AssessmentEvidencePayload]
    ) -> list[AssessmentEvidencePayload]:
        return _ordered_evidence(value)


class DeviceProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: AssessmentText | None = None
    product_family: AssessmentText | None = None
    model: AssessmentText | None = None
    confidence: AssessmentConfidence
    evidence: list[AssessmentEvidencePayload] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_ITEMS,
    )
    conflicts: list[AssessmentReason] = Field(
        default_factory=list,
        max_length=MAX_CONFLICTS,
    )
    limitations: list[AssessmentReason] = Field(
        default_factory=list,
        max_length=MAX_LIMITATIONS,
    )

    @field_validator("evidence")
    @classmethod
    def order_evidence(
        cls, value: list[AssessmentEvidencePayload]
    ) -> list[AssessmentEvidencePayload]:
        return _ordered_evidence(value)


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
    machine_type: MachineType | None = None
    device_profile: DeviceProfilePayload | None = None


class FindingPayload(BaseModel):
    ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    unit_id: Annotated[int | None, Field(default=None, ge=0, le=255)] = None
    protocol: Literal["tcp", "udp"] | None = None
    service: str | None = None
    source: str | None = None
    source_script: str | None = None
    # Internal reconciliation identity. It is excluded from the wire payload.
    issue_key: str | None = Field(default=None, exclude=True)
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
    assessment_policy_version: constr(min_length=1, strip_whitespace=True) | None = None
    exposures: list[ExposurePayload] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assessment_snapshot(self) -> ScanPayload:
        has_host_assessment = any(
            host.machine_type is not None or host.device_profile is not None
            for host in self.hosts
        )
        if self.assessment_policy_version is None:
            if self.exposures or has_host_assessment:
                raise ValueError(
                    "legacy payloads cannot carry exposures or host assessment"
                )
            return self

        incomplete_hosts = [
            str(host.ip)
            for host in self.hosts
            if host.machine_type is None or host.device_profile is None
        ]
        if incomplete_hosts:
            raise ValueError("current payloads require assessment for every host")

        open_endpoints = {
            (str(host.ip), port.protocol, port.port)
            for host in self.hosts
            for port in host.ports
            if port.state == "open"
        }
        assessed_endpoints = [
            (str(exposure.ip), exposure.protocol, exposure.port)
            for exposure in self.exposures
        ]
        if len(assessed_endpoints) != len(set(assessed_endpoints)):
            raise ValueError("current payloads cannot duplicate endpoint assessments")
        if set(assessed_endpoints) != open_endpoints:
            raise ValueError(
                "current payloads require exactly one exposure per open endpoint"
            )
        return self
