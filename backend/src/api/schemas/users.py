from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    role: Literal["admin", "viewer"]


class OrgMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    role: Literal["admin", "viewer"]
    last_seen_at: datetime | None


class OrgMemberListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[OrgMember]


class UpdateUserRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["admin", "viewer"]
