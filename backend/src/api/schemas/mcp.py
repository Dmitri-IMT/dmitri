from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class McpInfo(BaseModel):
    enabled: bool
    url: str | None


class McpAuthorizationView(BaseModel):
    client_name: str
    redirect_uri: str
    organization: str
    email: str
    scope: Literal["dmitri:read"] = "dmitri:read"


class McpConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_token: str = Field(
        min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$"
    )
    approve: bool


class McpConsentResponse(BaseModel):
    redirect_url: str


class McpConnectionView(BaseModel):
    id: UUID
    client_name: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None


class McpConnectionList(BaseModel):
    data: list[McpConnectionView]


class McpErrorBody(BaseModel):
    code: str
    message: str
    details: dict | None = None


class McpErrorResponse(BaseModel):
    error: McpErrorBody
