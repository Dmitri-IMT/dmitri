from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

UpdatePhase = Literal[
    "requested", "preparing", "installing", "verifying", "awaiting_confirmation",
    "recovering", "succeeded", "failed", "expired", "rolled_back", "needs_intervention",
]
UpdateErrorCode = Literal[
    "device_busy", "session_replaced", "request_expired", "release_not_allowed",
    "version_conflict", "metadata_untrusted", "metadata_expired", "artifact_mismatch",
    "unsupported_platform", "prerequisite_missing", "insufficient_resources",
    "package_manager_busy", "install_failed", "local_health_failed", "recovery_failed",
    "state_corrupt",
]
LocalOutcome = Literal["succeeded", "failed", "rolled_back", "needs_intervention"]


class AgentProtocolSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_versions: list[Literal[1]]
    capabilities: list[Literal["scan_finalization_v1"]]


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


class AgentUpdateHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[UpdateOperationView]
    next_cursor: str | None = None
