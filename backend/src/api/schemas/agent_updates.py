from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

UpdatePhase = Literal[
    "requested",
    "preparing",
    "installing",
    "verifying",
    "awaiting_confirmation",
    "recovering",
    "succeeded",
    "failed",
    "expired",
    "rolled_back",
    "needs_intervention",
]
UpdateErrorCode = Literal[
    "device_busy",
    "session_replaced",
    "request_expired",
    "release_not_allowed",
    "version_conflict",
    "metadata_untrusted",
    "metadata_expired",
    "artifact_mismatch",
    "unsupported_platform",
    "prerequisite_missing",
    "insufficient_resources",
    "package_manager_busy",
    "install_failed",
    "local_health_failed",
    "recovery_failed",
    "state_corrupt",
]
LocalOutcome = Literal["succeeded", "failed", "rolled_back", "needs_intervention"]


class AgentProtocolSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_versions: list[Literal[1]]
    capabilities: list[Literal["scan_finalization_v1"]]


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: UUID
    expected_observed_version: str = Field(min_length=1, max_length=128)


class ReleaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: UUID
    package: Literal["hardware-agent"]
    upstream_version: str
    package_version: str
    architecture: str
    suite: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    required_protocol_version: int = Field(ge=1)
    required_updater_version: int = Field(ge=1)
    published_at: datetime
    release_notes: str = Field(max_length=4000)


class AgentUpdateAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    availability: Literal["available", "up_to_date", "unknown", "unavailable"]
    release: ReleaseSummary | None = None
    catalogue_checked_at: datetime | None
    catalogue_valid_until: datetime | None
    device_readiness: Literal[
        "ready", "offline", "revoked", "bootstrap_required", "busy", "unknown"
    ]


class UpdateOperationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: UUID
    agent_id: UUID
    release_id: UUID
    previous_version: str | None
    previous_package_version: str | None
    target_version: str
    target_package_version: str
    observed_version: str | None
    observed_package_version: str | None
    phase: UpdatePhase
    local_outcome: LocalOutcome | None
    error_code: UpdateErrorCode | None
    actor_display_snapshot: str
    requested_at: datetime
    claimed_at: datetime | None
    local_completed_at: datetime | None
    confirmed_at: datetime | None
    last_contact_at: datetime | None


class AgentUpdateEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(gt=0)
    phase: UpdatePhase
    local_outcome: LocalOutcome | None = None
    observed_version: str | None = None
    observed_package_version: str | None = None
    occurred_at: datetime
    error_code: UpdateErrorCode | None = None


class AgentUpdateHelloContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: UUID
    invocation_id: UUID


class AgentUpdateClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    release_id: UUID
    target_package_version: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentUpdateClaimReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: UUID
    session_id: UUID
    release_id: UUID
    target_package_version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_deadline: datetime


class AgentUpdateEvidence(BaseModel):
    """Small, closed health evidence allowlist; never accepts logs or config."""

    model_config = ConfigDict(extra="forbid")

    package_status: Literal["configured"] | None = None
    service_active: bool | None = None
    health_check: Literal["passed", "failed"] | None = None


class AgentUpdateEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(gt=0)
    phase: UpdatePhase
    local_outcome: LocalOutcome | None = None
    observed_version: str | None = Field(default=None, min_length=1, max_length=128)
    package_version: str | None = Field(default=None, min_length=1, max_length=128)
    invocation_id: UUID | None = None
    session_id: UUID
    occurred_at: datetime
    error_code: UpdateErrorCode | None = None
    evidence: AgentUpdateEvidence | None = None


class AgentUpdateEventAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ack_sequence: int = Field(gt=0)


class UpdateProtocolErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "not_found",
        "device_revoked",
        "release_not_allowed",
        "artifact_mismatch",
        "session_replaced",
        "request_expired",
        "authorization_expired",
        "claim_state_invalid",
        "illegal_transition",
        "sequence_conflict",
        "sequence_out_of_order",
        "claim_required",
        "local_health_evidence_required",
        "hello_confirmation_required",
        "recovery_required",
        "invalid_event_time",
        "invalid_event_combination",
    ]
    message: str
    details: dict[str, object]


class UpdateProtocolErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: UpdateProtocolErrorDetail


class AgentUpdateHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[UpdateOperationView]
    next_cursor: str | None = None


class _UpdateErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    details: dict[str, object]


class UpdateBusyError(_UpdateErrorDetail):
    code: Literal["device_busy"]


class UpdateVersionConflictError(_UpdateErrorDetail):
    code: Literal["version_conflict"]


class UpdateReleaseNotAllowedError(_UpdateErrorDetail):
    code: Literal["release_not_allowed"]


class UpdateIdempotencyConflictError(_UpdateErrorDetail):
    code: Literal["idempotency_conflict"]


class UpdateOfflineError(_UpdateErrorDetail):
    code: Literal["device_offline"]


class UpdateBootstrapRequiredError(_UpdateErrorDetail):
    code: Literal["bootstrap_required"]


class UpdateCatalogUnavailableError(_UpdateErrorDetail):
    code: Literal["release_check_unavailable"]


class UpdateRevokedError(_UpdateErrorDetail):
    code: Literal["device_revoked"]


class UpdateForbiddenError(_UpdateErrorDetail):
    code: Literal["forbidden"]


class UpdateUnauthorizedError(_UpdateErrorDetail):
    code: Literal["unauthorized"]


UpdateConflictDetail = Annotated[
    Union[
        UpdateBusyError,
        UpdateVersionConflictError,
        UpdateReleaseNotAllowedError,
        UpdateIdempotencyConflictError,
    ],
    Field(discriminator="code"),
]
UpdateUnavailableDetail = Annotated[
    Union[
        UpdateOfflineError,
        UpdateBootstrapRequiredError,
        UpdateCatalogUnavailableError,
    ],
    Field(discriminator="code"),
]
UpdateForbiddenDetail = Annotated[
    Union[UpdateRevokedError, UpdateForbiddenError],
    Field(discriminator="code"),
]


class UpdateConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: UpdateConflictDetail


class UpdateUnavailableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: UpdateUnavailableDetail


class UpdateForbiddenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: UpdateForbiddenDetail


class UpdateUnauthorizedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: UpdateUnauthorizedError
