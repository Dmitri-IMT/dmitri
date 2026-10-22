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
    StrictBool,
    StrictInt,
    StrictStr,
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


class OpcUaEndpointPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_url: constr(min_length=1, max_length=256)
    security_policy_uri: constr(min_length=1, max_length=256)
    security_mode: Literal["None", "Sign", "SignAndEncrypt"]
    transport_profile_uri: constr(min_length=1, max_length=256)
    security_level: Annotated[int, Field(ge=0, le=255, strict=True)]
    user_token_count: Annotated[int, Field(ge=0, le=8, strict=True)]
    user_token_types: list[
        Literal["Anonymous", "UserName", "Certificate", "IssuedToken"]
    ] = Field(max_length=8)
    target_matches: StrictBool


class OpcUaIdentityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_uri: constr(max_length=128) | None = None
    product_uri: constr(max_length=128) | None = None
    application_name: constr(max_length=128) | None = None
    application_type: (
        Literal["Server", "Client", "ClientAndServer", "DiscoveryServer"] | None
    ) = None


class OpcUaPhasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "completed",
        "partial",
        "failed",
        "timed_out",
        "skipped",
        "denied",
        "unsupported_security",
    ]
    reason_codes: list[
        Literal[
            "timeout",
            "endpoint_discovery_failed",
            "endpoint_target_mismatch",
            "endpoint_limit",
            "message_size_limit",
            "request_budget_exhausted",
            "service_not_allowed",
            "service_error",
            "invalid_response",
            "helper_unavailable",
            "cancelled",
            "host_deadline",
            "stage_deadline",
            "global_deadline",
            "decode_limit",
            "byte_limit",
            "opaque_node_id_omitted",
            "observation_size_limit",
            "decode_error",
            "authentication_required",
            "anonymous_denied",
            "security_configuration_required",
            "external_reference",
            "page_limit",
            "node_limit",
            "depth_limit",
            "no_eligible_variables",
            "service_limit",
        ]
    ] = Field(max_length=16)
    truncated: StrictBool
    observed_at: datetime


class OpcUaObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    inventory_phase: OpcUaPhasePayload
    identity: OpcUaIdentityPayload | None = None
    certificate_sha256: constr(pattern=r"^[0-9a-f]{64}$") | None = None
    endpoints: list[OpcUaEndpointPayload] = Field(max_length=16)
    mapping: "OpcUaMappingPayload | None" = None


class OpcUaMappedReferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_node_id: constr(min_length=1, max_length=256)
    target_node_id: constr(min_length=1, max_length=256)
    reference_type_id: constr(min_length=1, max_length=256)
    is_forward: StrictBool


class OpcUaMappedNodePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: constr(min_length=1, max_length=256)
    parent_node_id: constr(max_length=256) | None = None
    depth: Annotated[int, Field(ge=0, le=4, strict=True)]
    node_class: Literal["Object", "Variable"]
    browse_name: constr(max_length=128) | None = None
    display_name: constr(max_length=128) | None = None
    data_type: constr(max_length=256) | None = None
    value_rank: int | None = None
    access_level: Annotated[int | None, Field(ge=0, le=255, strict=True)] = None
    user_access_level: Annotated[int | None, Field(ge=0, le=255, strict=True)] = None
    value_read_status: Literal["Good", "Denied", "Error", "Skipped"] | None = None


class OpcUaSecurityFactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: constr(min_length=1, max_length=256)
    source: Literal["get_endpoints"]
    status: Literal["Good", "Bad"]


class OpcUaMappingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: OpcUaPhasePayload
    nodes: list[OpcUaMappedNodePayload] = Field(max_length=128)
    references: list[OpcUaMappedReferencePayload] = Field(
        default_factory=list, max_length=512
    )
    references_observed: Annotated[int, Field(ge=0, le=512, strict=True)]
    value_reads_attempted: Annotated[int, Field(ge=0, le=8, strict=True)]
    selected_endpoint_index: Annotated[int, Field(ge=0, le=15, strict=True)] | None
    anonymous_session_activated: StrictBool | None
    browse_succeeded: StrictBool | None
    application_value_read_succeeded: StrictBool | None
    value_good_count: Annotated[int, Field(ge=0, le=8, strict=True)]
    security_mode: OpcUaSecurityFactPayload
    security_policy: OpcUaSecurityFactPayload


class OpcUaTcpServicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["opcua_tcp"]
    port: Annotated[int, Field(ge=1, le=65535, strict=True)]
    confidence: Literal["suspected", "confirmed"]
    evidence_sources: list[constr(min_length=1, max_length=64)] = Field(
        default_factory=list, max_length=8
    )
    write_requests_sent: Annotated[int, Field(default=0, ge=0, strict=True)]
    observation: OpcUaObservationPayload


class HostPayload(BaseModel):
    ip: IPv4Address
    mac: constr(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") | None = None
    hostname: constr(min_length=1)
    vendor: constr(min_length=1)
    operating_system: OperatingSystemDetection | None = None
    ports: list[PortPayload] = Field(default_factory=list)
    industrial_services: list[ModbusTcpServicePayload | OpcUaTcpServicePayload] = Field(
        default_factory=list
    )

    @field_validator("industrial_services", mode="before")
    @classmethod
    def normalize_legacy_modbus_protocol(cls, value):
        if not isinstance(value, list):
            return value
        normalized = []
        for item in value:
            if isinstance(item, dict) and "protocol" not in item and "units" in item:
                item = {**item, "protocol": "modbus_tcp"}
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
    source_script: constr(min_length=1, max_length=64, strip_whitespace=True) | None = (
        None
    )
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
    ip: IPv4Address | None = None
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    unit_id: Annotated[int | None, Field(default=None, ge=0, le=255)] = None
    protocol: Literal["tcp", "udp"] | None = None
    service: str | None = None
    source: str | None = None
    source_script: str | None = None
    # Optional reconciliation identity used to bind evidence to its condition.
    issue_key: constr(min_length=1, max_length=256, strip_whitespace=True) | None = None
    cve_id: constr(pattern=r"^CVE-[0-9]{4}-[0-9]{4,}$") | None = None
    cvss_score: Annotated[float | None, Field(default=None, ge=0, le=10)]
    severity: Literal["low", "medium", "high", "critical"]
    title: constr(min_length=3)
    description: constr(min_length=3)
    recommendation: constr(min_length=3)
    evidence: constr(min_length=3)
    references: list[constr(min_length=1)] = Field(default_factory=list)
    evidence_observations: list[FindingEvidenceObservationPayload] = Field(
        default_factory=list, max_length=16
    )
    evidence_truncated: bool = False


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
    stage: Literal["ports", "deep_inspection", "ot_inspection", "targeted_assessment"]
    port: Annotated[int | None, Field(default=None, ge=1, le=65535)]
    protocol: Literal["tcp", "udp"] | None = None
    tool: constr(min_length=1, max_length=64) | None = None
    outcome: Literal["completed", "partial", "failed", "timed_out", "skipped"]
    reason_code: constr(min_length=1, max_length=64) | None = None
    evidence_source: Literal[
        "nmap_ports",
        "nmap_nse",
        "service_recovery",
        "port_discovery",
        "modbus_inspection",
        "opcua_inspection",
        "targeted_tool",
        "targeted_tool_partial_report",
        "not_run",
    ]
    issue_keys: list[constr(min_length=1, max_length=256)] = Field(default_factory=list)
    observations: list[CoverageObservationPayload] = Field(default_factory=list)


class ScanPayload(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: SubnetCIDR
    scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"]
    hosts: list[HostPayload] = Field(default_factory=list)
    findings: list[FindingPayload] = Field(default_factory=list)
    coverage: list[CoverageUnitPayload] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] | None = None
    assessment_policy_version: constr(min_length=1, strip_whitespace=True) | None = None
    exposures: list[ExposurePayload] = Field(default_factory=list)
    finding_evidence_policy_version: (
        constr(min_length=1, max_length=64, strip_whitespace=True) | None
    ) = None
    finding_observations: list[FindingEvidenceObservationPayload] = Field(
        default_factory=list, max_length=512
    )
    finding_observations_truncated: bool = False

    @model_validator(mode="after")
    def validate_assessment_snapshot(self) -> ScanPayload:
        has_evidence_metadata = bool(
            self.finding_observations
            or self.finding_observations_truncated
            or any(
                f.evidence_observations or f.evidence_truncated for f in self.findings
            )
        )
        if self.finding_evidence_policy_version is None and has_evidence_metadata:
            raise ValueError("finding evidence metadata requires a policy version")
        hosts_by_ip = {str(host.ip) for host in self.hosts}
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
                if observation.ip is not None and observation.ip != finding.ip:
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
                    raise ValueError("finding observation unit must match its finding")
        for observation in self.finding_observations:
            if observation.result == "positive":
                raise ValueError("standalone finding observations cannot be positive")
            if observation.ip is not None and str(observation.ip) not in hosts_by_ip:
                raise ValueError(
                    "standalone finding observation IP must belong to the scan"
                )
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
