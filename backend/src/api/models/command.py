from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import LargeBinary
from sqlmodel import Field, SQLModel

from api.models.persistence import utc_now


class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id", index=True)
    display_name: str
    secret_ciphertext: bytes = Field(sa_type=LargeBinary)
    secret_nonce: bytes = Field(sa_type=LargeBinary)
    secret_key_version: int
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Command(SQLModel, table=True):
    __tablename__ = "commands"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id", index=True)
    agent_id: UUID = Field(foreign_key="agents.id", index=True)
    scan_id: UUID = Field(foreign_key="scans.scan_id", unique=True)
    scan_mode: str
    subnet: str
    status: str
    error_code: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    delivered_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
