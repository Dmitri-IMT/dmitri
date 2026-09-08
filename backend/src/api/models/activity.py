from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from api.models.persistence import UTC_TIMESTAMP

ActivityKind = Literal[
    "scan_started",
    "scan_finished",
    "scan_failed",
    "machine_first_seen",
    "role_changed",
    "member_invited",
    "invite_revoked",
    "member_removed",
    "account_deleted",
]

ACTIVITY_KINDS: tuple[str, ...] = get_args(ActivityKind)

_ACTIVITY_KIND_CHECK = "kind IN (" + ", ".join(f"'{k}'" for k in ACTIVITY_KINDS) + ")"


class ActivityRecord(SQLModel, table=True):
    __tablename__ = "activity"
    __table_args__ = (CheckConstraint(_ACTIVITY_KIND_CHECK, name="ck_activity_kind"),)

    id: int | None = Field(default=None, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="orgs.id")
    kind: str
    occurred_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    actor_user_id: UUID | None = Field(default=None)
    subject_id: UUID | None = Field(default=None)
    payload: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=False),
    )
