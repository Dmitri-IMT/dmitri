from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, Column
from sqlmodel import Field, SQLModel

from api.models.persistence import UTC_TIMESTAMP, utc_now


class McpClient(SQLModel, table=True):
    __tablename__ = "mcp_clients"

    id: str = Field(primary_key=True)
    metadata_json: dict = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class McpConnection(SQLModel, table=True):
    __tablename__ = "mcp_connections"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    org_id: UUID = Field(foreign_key="orgs.id", ondelete="CASCADE")
    client_id: str = Field(foreign_key="mcp_clients.id")
    resource: str
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    expires_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    revoked_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    last_used_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)


class McpAuthorization(SQLModel, table=True):
    __tablename__ = "mcp_authorizations"

    request_hash: str = Field(primary_key=True)
    client_id: str = Field(foreign_key="mcp_clients.id")
    params_json: dict = Field(sa_column=Column(JSON, nullable=False))
    expires_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    decided_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    connection_id: UUID | None = Field(
        default=None, foreign_key="mcp_connections.id", ondelete="CASCADE"
    )
    code_hash: str | None = Field(default=None, unique=True, index=True)
    exchanged_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)


class McpCredential(SQLModel, table=True):
    __tablename__ = "mcp_credentials"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('access', 'refresh')", name="ck_mcp_credentials_kind"
        ),
    )

    token_hash: str = Field(primary_key=True)
    connection_id: UUID = Field(
        foreign_key="mcp_connections.id", ondelete="CASCADE", index=True
    )
    kind: str
    expires_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    rotated_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
