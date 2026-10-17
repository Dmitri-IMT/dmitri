from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BIGINT, JSON, CheckConstraint, Column, Index, text
from sqlmodel import Field, SQLModel, UniqueConstraint

from api.models.persistence import UTC_TIMESTAMP, utc_now

RELEASE_PHASES = (
    "requested", "preparing", "installing", "verifying", "awaiting_confirmation",
    "recovering", "succeeded", "failed", "expired", "rolled_back", "needs_intervention",
)
UPDATE_ERROR_CODES = (
    "device_busy", "session_replaced", "request_expired", "release_not_allowed",
    "version_conflict", "metadata_untrusted", "metadata_expired", "artifact_mismatch",
    "unsupported_platform", "prerequisite_missing", "insufficient_resources",
    "package_manager_busy", "install_failed", "local_health_failed", "recovery_failed",
    "state_corrupt",
)
LOCAL_OUTCOMES = ("succeeded", "failed", "rolled_back", "needs_intervention")
_PHASE_CHECK = "phase IN (" + ",".join(f"'{value}'" for value in RELEASE_PHASES) + ")"
_OUTCOME_CHECK = (
    "local_outcome IS NULL OR local_outcome IN ("
    + ",".join(f"'{value}'" for value in LOCAL_OUTCOMES)
    + ")"
)
_ERROR_CHECK = (
    "error_code IS NULL OR error_code IN ("
    + ",".join(f"'{value}'" for value in UPDATE_ERROR_CODES)
    + ")"
)


class AgentRelease(SQLModel, table=True):
    __tablename__ = "agent_releases"
    __table_args__ = (
        UniqueConstraint(
            "package",
            "package_version",
            "architecture",
            name="uq_agent_releases_package_version_arch",
        ),
        CheckConstraint("package = 'hardware-agent'", name="ck_agent_releases_package"),
        CheckConstraint("size_bytes > 0", name="ck_agent_releases_size_positive"),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name="ck_agent_releases_sha256"
        ),
        CheckConstraint(
            "required_protocol_version >= 1 AND required_updater_version >= 1",
            name="ck_agent_releases_requirements",
        ),
        Index("ix_agent_releases_approved_published", "approved_at", "published_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_commit: str
    upstream_version: str
    package: str = "hardware-agent"
    package_version: str
    architecture: str
    suite: str
    sha256: str
    size_bytes: int = Field(sa_type=BIGINT)
    required_protocol_version: int
    required_updater_version: int
    release_notes: str = ""
    published_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    approved_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    withdrawn_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class AgentUpdate(SQLModel, table=True):
    __tablename__ = "agent_updates"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "agent_id",
            "idempotency_key",
            name="uq_agent_updates_idempotency",
        ),
        CheckConstraint(_PHASE_CHECK, name="ck_agent_updates_phase"),
        CheckConstraint(_OUTCOME_CHECK, name="ck_agent_updates_local_outcome"),
        CheckConstraint(_ERROR_CHECK, name="ck_agent_updates_error_code"),
        CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_agent_updates_request_digest",
        ),
        CheckConstraint(
            "idempotency_key <> ''", name="ck_agent_updates_idempotency_key"
        ),
        Index("ix_agent_updates_agent_created", "agent_id", "created_at"),
        Index("ix_agent_updates_deadline", "phase", "claim_deadline"),
        Index(
            "uq_agent_updates_active_agent",
            "agent_id",
            unique=True,
            postgresql_where=text(
                "phase IN ('requested','preparing','installing','verifying',"
                "'awaiting_confirmation','recovering','needs_intervention')"
            ),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id", index=True)
    agent_id: UUID = Field(foreign_key="agents.id", index=True)
    actor_id: UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )
    actor_display_snapshot: str
    idempotency_key: str
    request_digest: str
    release_id: UUID = Field(foreign_key="agent_releases.id")
    previous_version: str | None = None
    previous_package_version: str | None = None
    target_version: str
    target_package_version: str
    session_id: UUID | None = None
    invocation_id: UUID | None = None
    phase: str = "requested"
    local_outcome: str | None = None
    observed_version: str | None = None
    observed_package_version: str | None = None
    error_code: str | None = None
    claim_deadline: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    authorization_deadline: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    requested_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    claimed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    mutation_started_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    local_completed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    confirmed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    last_contact_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class AgentUpdateEvent(SQLModel, table=True):
    __tablename__ = "agent_update_events"
    __table_args__ = (
        UniqueConstraint(
            "update_id", "sequence", name="uq_agent_update_events_sequence"
        ),
        CheckConstraint(
            "sequence > 0", name="ck_agent_update_events_sequence_positive"
        ),
        CheckConstraint(_PHASE_CHECK, name="ck_agent_update_events_phase"),
        CheckConstraint(_OUTCOME_CHECK, name="ck_agent_update_events_local_outcome"),
        CheckConstraint(_ERROR_CHECK, name="ck_agent_update_events_error_code"),
        CheckConstraint(
            "body_digest ~ '^[0-9a-f]{64}$'",
            name="ck_agent_update_events_body_digest",
        ),
        Index("ix_agent_update_events_created", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    update_id: UUID = Field(foreign_key="agent_updates.id", index=True)
    sequence: int
    body_digest: str
    phase: str
    local_outcome: str | None = None
    observed_version: str | None = None
    observed_package_version: str | None = None
    invocation_id: UUID | None = None
    session_id: UUID | None = None
    occurred_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    error_code: str | None = None
    evidence_json: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class AgentReleaseCatalogState(SQLModel, table=True):
    __tablename__ = "agent_release_catalog_state"
    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="ck_agent_release_catalog_singleton"),
        CheckConstraint("generation >= 0", name="ck_agent_release_catalog_generation"),
        CheckConstraint(
            "digest IS NULL OR digest ~ '^[0-9a-f]{64}$'",
            name="ck_agent_release_catalog_digest",
        ),
    )

    singleton_id: int = Field(default=1, primary_key=True)
    generation: int = Field(default=0, sa_type=BIGINT)
    digest: str | None = None
    validated_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    valid_until: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
