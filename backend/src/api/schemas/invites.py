from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, constr

from api.services.passwords import MIN_LENGTH


class CreateInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    role: Literal["admin", "viewer"]


class InviteCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invite_token: str
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    password: constr(min_length=MIN_LENGTH)


class InviteLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class InviteLookupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    role: Literal["admin", "viewer"]
    org_name: str


class PendingInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invite_id: UUID
    email: str
    role: Literal["admin", "viewer"]
    expires_at: datetime


class PendingInviteListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[PendingInvite]
