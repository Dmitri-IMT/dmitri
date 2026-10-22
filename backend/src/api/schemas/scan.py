from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    constr,
    field_validator,
    model_validator,
)

from api.core.machine_type import MachineType
from api.core.scan_mode import ScanMode

from .industrial import IndustrialServicePayload, ModbusTcpServicePayload
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

# metadata.terminated_by value the Pi runner writes when an operator stops a scan.
TERMINATED_BY_USER_CANCEL = "user_cancel"

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
    industrial_services: list[IndustrialServicePayload] = Field(default_factory=list)

    @field_validator("industrial_services", mode="before")
    @classmethod
    def normalize_legacy_modbus_protocol(cls, value):
        if not isinstance(value, list):
            return value
        normalized = []
        for item in value:
            if isinstance(item, dict) and "protocol" not in item:
                # Validate the whole legacy shape before injecting its default tag.
                # This accepts defaulted Modbus fields such as omitted ``units``
                # while rejecting untagged UA and unknown payloads.
                modbus = ModbusTcpServicePayload.model_validate(item)
                normalized.append(modbus.model_dump(mode="python"))
            else:
                normalized.append(item)
        return normalized
    machine_type: MachineType | None = None
    device_profile: DeviceProfilePayload | None = None


class FindingEvidenceObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)] = None
    protocol: Literal["tcp", "udp"] | None = None
    unit_id: Annotated[int | None, Field(default=None, ge=0, le=255)] = None
    condition_key: constr(min_length=1, max_length=256, strip_whitespace=True)
    method: Literal[
        "version_correlation",
        "configuration_observation",
        "specific_check",
        "textual_reference",
        "unknown",
    ]
    result: Literal["positive", "negative", "inconclusive"]
    source: constr(min_length=1, max_length=64, strip_whitespace=True)
    source_script: constr(
        min_length=1, max_length=64, strip_whitespace=True
    ) | None = None
    rule_id: constr(min_length=1, max_length=128, strip_whitespace=True)
    rule_version: constr(min_length=1, max_length=64, strip_whitespace=True)
    evidence: constr(min_length=1, max_length=512, strip_whitespace=True)
    facts: dict[
        constr(min_length=1, max_length=64, strip_whitespace=True),
        Annotated[StrictStr, Field(max_length=160)] | StrictInt | StrictBool,
    ] = Field(default_factory=dict, max_length=8)

    @field_validator("facts")
    @classmethod
    def validate_fact_values(cls, value):
        return value



class FindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    protocol: Literal["tcp", "udp"] | None = None
    service: str | None = None
    source: str | None = None
    source_script: str | None = None
    issue_key: constr(min_length=1, max_length=256, strip_whitespace=True) | None = None
    cve_id: constr(pattern=r"^CVE-[0-9]{4}-[0-9]{4,}$") | None = None
    cvss_score: Annotated[float | None, Field(default=None, ge=0, le=10)]
    severity: Literal["low", "medium", "high", "critical"]
    title: constr(min_length=3)
    description: constr(min_length=3)
    recommendation: constr(min_length=3)
    evidence: constr(min_length=3)
    references: list[constr(min_length=1)] = Field(default_factory=list)
    unit_id: Annotated[int | None, Field(default=None, ge=0, le=255)] = None
    evidence_observations: list[FindingEvidenceObservationPayload] = Field(
        default_factory=list, max_length=16
    )
    evidence_truncated: bool = False


EvidenceCompleteness = Literal["complete", "partial", "unknown"]


class CoverageObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_key: constr(min_length=1, max_length=512)
    kind: Literal[
        "administration", "api_surface", "service_identity", "device_identity"
    ]
    summary: constr(min_length=1, max_length=512)
    evidence: constr(min_length=1, max_length=512)
    path: constr(max_length=256) | None = None
    rule_id: constr(max_length=128) | None = None
    policy_version: constr(max_length=64) | None = None


class CoverageUnitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip: IPv4Address
    stage: Literal[
        "ports", "deep_inspection", "ot_inspection", "targeted_assessment"
    ]
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    protocol: Literal["tcp", "udp"] | None = None
    tool: constr(min_length=1, max_length=64) | None = None
    outcome: Literal["completed", "partial", "failed", "timed_out", "skipped"]
    reason_code: constr(min_length=1, max_length=64) | None = None
    evidence_source: Literal[
        "nmap_nse", "service_recovery", "nmap_ports", "port_discovery",
        "modbus_inspection", "opcua_inspection", "targeted_tool",
        "targeted_tool_partial_report", "not_run",
    ]
    issue_keys: list[constr(min_length=1, max_length=256)] = Field(default_factory=list)
    observations: list[CoverageObservationPayload] = Field(default_factory=list)


class ScanIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: ScanMode
    hosts: list[HostPayload]
    findings: list[FindingPayload]
    coverage: list[CoverageUnitPayload] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None
    assessment_policy_version: constr(min_length=1, strip_whitespace=True) | None = None
    exposures: list[ExposurePayload] = Field(default_factory=list)
    finding_evidence_policy_version: constr(
        min_length=1, max_length=64, strip_whitespace=True
    ) | None = None
    finding_observations: list[FindingEvidenceObservationPayload] = Field(
        default_factory=list, max_length=512
    )
    finding_observations_truncated: bool = False

    @model_validator(mode="after")
    def validate_assessment_snapshot(self) -> ScanIngestRequest:
        self._validate_finding_evidence()
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

    def _validate_finding_evidence(self) -> None:
        has_evidence_metadata = bool(
            self.finding_observations
            or self.finding_observations_truncated
            or any(
                f.evidence_observations or f.evidence_truncated
                for f in self.findings
            )
        )
        if self.finding_evidence_policy_version is None and has_evidence_metadata:
            raise ValueError("finding evidence metadata requires a policy version")
        hosts = {str(host.ip) for host in self.hosts}
        for finding in self.findings:
            for observation in finding.evidence_observations:
                expected_condition = (
                    finding.cve_id
                    if observation.method == "version_correlation"
                    or (
                        observation.method == "specific_check"
                        and (
                            observation.rule_id.endswith("ms17-010")
                            or finding.issue_key == finding.cve_id
                        )
                    )
                    else finding.issue_key
                )
                if (
                    expected_condition is not None
                    and observation.condition_key != expected_condition
                ):
                    raise ValueError(
                        "finding observation condition must match its finding"
                    )
                if observation.ip is not None and str(observation.ip) != str(
                    finding.ip
                ):
                    raise ValueError("finding observation IP must match its finding")
                if observation.port is not None and observation.port != finding.port:
                    raise ValueError("finding observation port must match its finding")
                if (
                    observation.protocol is not None
                    and observation.protocol != finding.protocol
                ):
                    raise ValueError(
                        "finding observation protocol must match its finding"
                    )
                if (
                    observation.unit_id is not None
                    and observation.unit_id != finding.unit_id
                ):
                    raise ValueError(
                        "finding observation unit must match its finding"
                    )
        for observation in self.finding_observations:
            if observation.result == "positive":
                raise ValueError("standalone finding observations cannot be positive")
            if observation.ip is not None and str(observation.ip) not in hosts:
                raise ValueError(
                    "standalone finding observation IP must belong to the scan"
                )


class ScanIngestAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    scan_id: UUID
    hosts_received: Annotated[int, Field(ge=0)]
    status: Literal["accepted"]
