from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

UaClientStatus = Literal["ok", "error"]
UaClientError = Literal[
    "invalid_target",
    "unsupported_operation",
    "timeout",
    "message_size_limit",
    "request_budget_exhausted",
    "service_not_allowed",
    "service_error",
    "helper_unavailable",
    "invalid_response",
]


@dataclass(frozen=True, slots=True)
class OpcUaEndpoint:
    endpoint_url: str
    security_policy_uri: str
    security_mode: str
    transport_profile_uri: str
    security_level: int
    user_token_count: int
    user_token_types: tuple[str, ...] = ()
    application_uri: str | None = None
    product_uri: str | None = None
    application_name: str | None = None
    application_type: str | None = None
    certificate_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class OpcUaInventoryEndpoint:
    endpoint_url: str
    security_policy_uri: str
    security_mode: str
    transport_profile_uri: str
    security_level: int
    user_token_count: int
    target_matches: bool
    user_token_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpcUaInventory:
    protocol: Literal["opcua_tcp"]
    port: int
    confidence: Literal["suspected", "confirmed"]
    evidence_sources: tuple[str, ...]
    inventory_status: Literal["completed", "partial", "failed", "timed_out"]
    observed_at: datetime
    endpoints: tuple[OpcUaInventoryEndpoint, ...] = ()
    identity: dict[str, str | None] = field(default_factory=dict)
    certificate_sha256: str | None = None
    application_type: str | None = None
    reason_code: str | None = None
    reason_codes: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class OpcUaRequestStats:
    requests: dict[str, int] = field(default_factory=dict)
    requests_total: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    hello_limits: tuple[int, int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class OpcUaClientResult:
    status: UaClientStatus
    endpoints: tuple[OpcUaEndpoint, ...] = ()
    error: UaClientError | None = None
    stats: OpcUaRequestStats = field(default_factory=OpcUaRequestStats)
    endpoints_truncated: bool = False
    mapping: "OpcUaMappingResult | None" = None


@dataclass(frozen=True, slots=True)
class OpcUaMappedNode:
    node_id: str
    parent_node_id: str | None
    depth: int
    node_class: str
    browse_name: str | None = None
    display_name: str | None = None
    data_type: str | None = None
    value_rank: int | None = None
    access_level: int | None = None
    user_access_level: int | None = None
    value_read_status: str | None = None


@dataclass(frozen=True, slots=True)
class OpcUaMappedReference:
    source_node_id: str
    target_node_id: str
    reference_type_id: str
    is_forward: bool


@dataclass(frozen=True, slots=True)
class OpcUaMappingResult:
    status: str
    reason_codes: tuple[str, ...] = ()
    nodes: tuple[OpcUaMappedNode, ...] = ()
    references: tuple[OpcUaMappedReference, ...] = ()
    references_observed: int = 0
    value_reads_attempted: int = 0
    selected_endpoint_index: int | None = None
    anonymous_session_activated: bool | None = None
    browse_succeeded: bool | None = None
    application_value_read_succeeded: bool | None = None
    value_good_count: int = 0
    security_mode: dict[str, str] = field(default_factory=dict)
    security_policy: dict[str, str] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    truncated: bool = False
