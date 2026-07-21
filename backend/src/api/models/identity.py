from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, text
from sqlmodel import Field, SQLModel

from api.models.persistence import utc_now

_ROLE_CHECK = "role IN ('admin', 'viewer')"


class Org(SQLModel, table=True):
    __tablename__ = "orgs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utc_now)


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_org_email", "org_id", text("lower(email)"), unique=True),
        CheckConstraint(_ROLE_CHECK, name="ck_users_role"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id")
    email: str
    password_hash: str
    role: str
    password_changed_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)


class Invite(SQLModel, table=True):
    __tablename__ = "invites"
    __table_args__ = (CheckConstraint(_ROLE_CHECK, name="ck_invites_role"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="orgs.id")
    email: str
    role: str
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime
    consumed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
