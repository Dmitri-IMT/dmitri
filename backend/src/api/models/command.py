from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, LargeBinary
from sqlmodel import Field, SQLModel, UniqueConstraint

from api.models.persistence import UTC_TIMESTAMP, utc_now


class Agent(SQLModel, table=True):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("org_id", "public_key", name="uq_agents_org_public_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id", index=True)
    display_name: str
    public_key: bytes = Field(sa_type=LargeBinary)
    revoked_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    last_seen_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    connected_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    target_subnet: str | None = None
    observed_version: str | None = None
    observed_package_version: str | None = None
    version_observed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    version_observed_session_id: UUID | None = None


class AgentNonce(SQLModel, table=True):
    __tablename__ = "agent_nonces"
    __table_args__ = (
        UniqueConstraint("agent_id", "nonce", name="uq_agent_nonces_agent_id_nonce"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    agent_id: UUID = Field(foreign_key="agents.id")
    nonce: str
    expires_at: datetime = Field(index=True, sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class Command(SQLModel, table=True):
    __tablename__ = "commands"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id", index=True)
    agent_id: UUID = Field(foreign_key="agents.id", index=True)
    scan_id: UUID | None = Field(
        default=None, foreign_key="scans.scan_id", unique=True
    )
    scan_mode: str
    subnet: str
    nspi_options: dict[str, object] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    status: str
    error_code: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    delivered_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    started_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    completed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
