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

from api.core.machine_type import MachineType
from api.core.scan_mode import ScanMode

from .industrial import ModbusTcpServicePayload
from .operating_system import OperatingSystemDetection

SubnetCIDR = constr(
    pattern=r"^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$",
    strip_whitespace=True,
)

AssessmentConfidence = Literal["unknown", "low", "medium", "high"]
EvidenceKind = Literal[
    "manufacturer",
    "hostname",
    "operating_system",
    "service",
    "version",
    "banner",
    "certificate",
    "protocol",
    "port",
    "cpe",
    "industrial",
    "web_path",
]
ExposureRole = Literal[
    "administration",
    "data_store",
    "file_sharing",
    "remote_access",
    "proxy",
    "api",
    "device_control",
    "discovery",
    "media",
    "general_service",
    "unknown",
]
ExposureAttention = Literal["informational", "review", "priority"]
ExposureConfidence = Literal["low", "medium", "high"]

AssessmentText = constr(min_length=1, max_length=160, strip_whitespace=True)
AssessmentReason = constr(min_length=1, max_length=240, strip_whitespace=True)


class AssessmentEvidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    source: constr(min_length=1, max_length=80, strip_whitespace=True)
    value: constr(min_length=1, max_length=160, strip_whitespace=True)


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
        default_factory=list, max_length=12
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
        default_factory=list, max_length=12
    )
    conflicts: list[AssessmentReason] = Field(default_factory=list, max_length=5)
    limitations: list[AssessmentReason] = Field(default_factory=list, max_length=5)

    @field_validator("evidence")
    @classmethod
    def order_evidence(
        cls, value: list[AssessmentEvidencePayload]
    ) -> list[AssessmentEvidencePayload]:
        return _ordered_evidence(value)


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
    operating_system: OperatingSystemDetection | None = None
    ports: list[PortPayload]
    industrial_services: list[ModbusTcpServicePayload] = Field(default_factory=list)
    machine_type: MachineType | None = None
    device_profile: DeviceProfilePayload | None = None


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
    unit_id: Annotated[int | None, Field(default=None, ge=0, le=255)] = None


class ScanIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: ScanMode
    hosts: list[HostPayload]
    findings: list[FindingPayload]
    metadata: dict[str, str | int | float | bool] | None = None
    assessment_policy_version: constr(min_length=1, strip_whitespace=True) | None = None
    exposures: list[ExposurePayload] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assessment_snapshot(self) -> ScanIngestRequest:
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

        if any(
            host.machine_type is None or host.device_profile is None
            for host in self.hosts
        ):
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


class ScanIngestAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    scan_id: UUID
    hosts_received: Annotated[int, Field(ge=0)]
    status: Literal["accepted"]
