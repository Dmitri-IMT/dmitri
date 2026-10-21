from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
