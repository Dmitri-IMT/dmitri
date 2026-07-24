from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from api.models.persistence import UTC_TIMESTAMP, utc_now


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    family_id: UUID = Field(index=True)
    token_hash: str = Field(unique=True, index=True)
    family_expires_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    rotated_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    revoked_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    consumed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
