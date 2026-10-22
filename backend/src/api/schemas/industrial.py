"""Industrial / Modbus ingest models shared by scan ingest."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, constr

MAX_DEVICE_STRING_CHARS = 128
MAX_IDENTIFICATION_OBJECTS = 16
MAX_IDENTIFICATION_SOURCES = 8
MAX_ADDRESS_RANGES_PER_UNIT = 32

DeviceString = Annotated[str | None, Field(max_length=MAX_DEVICE_STRING_CHARS)]
ValueDigest = Annotated[
    str | None,
    Field(pattern=r"^hmac-sha256:[0-9a-f]{64}$"),
]


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
    # Older NSPi agents emitted additional read summaries (for example
    # ``value_sha256`` and ``nonzero_count``). They are not required for the
    # current UI, but must not cause the complete industrial observation to be
    # discarded during ingest.
    model_config = ConfigDict(extra="ignore")

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
    # Older agents included optional validation metadata on Modbus units.
    # Keep ingest backwards-compatible while retaining the typed fields used
    # by the current API and persistence layer.
    model_config = ConfigDict(extra="ignore")

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
    application_type: Literal[
        "Server", "Client", "ClientAndServer", "DiscoveryServer"
    ] | None = None


OpcUaPhaseStatus = Literal[
    "completed", "partial", "failed", "timed_out", "skipped", "denied",
    "unsupported_security",
]
OpcUaReasonCode = Literal[
    "timeout", "endpoint_discovery_failed", "endpoint_target_mismatch",
    "endpoint_limit", "message_size_limit", "request_budget_exhausted",
    "service_not_allowed", "service_error", "invalid_response",
    "helper_unavailable", "cancelled", "host_deadline", "stage_deadline",
    "global_deadline", "decode_limit", "byte_limit", "opaque_node_id_omitted",
    "observation_size_limit", "decode_error", "authentication_required",
    "anonymous_denied", "security_configuration_required", "external_reference",
    "page_limit", "node_limit", "depth_limit", "no_eligible_variables",
    "service_limit",
]


class OpcUaPhasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OpcUaPhaseStatus
    reason_codes: list[OpcUaReasonCode] = Field(max_length=16)
    truncated: StrictBool
    observed_at: datetime


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
    selected_endpoint_index: Annotated[int | None, Field(ge=0, le=15, strict=True)]
    anonymous_session_activated: StrictBool | None
    browse_succeeded: StrictBool | None
    application_value_read_succeeded: StrictBool | None
    value_good_count: Annotated[int, Field(ge=0, le=8, strict=True)]
    security_mode: OpcUaSecurityFactPayload
    security_policy: OpcUaSecurityFactPayload


class OpcUaObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    inventory_phase: OpcUaPhasePayload
    identity: OpcUaIdentityPayload | None = None
    certificate_sha256: constr(pattern=r"^[0-9a-f]{64}$") | None = None
    endpoints: list[OpcUaEndpointPayload] = Field(max_length=16)
    mapping: OpcUaMappingPayload | None = None


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


IndustrialServicePayload = Annotated[
    ModbusTcpServicePayload | OpcUaTcpServicePayload,
    Field(discriminator="protocol"),
]
