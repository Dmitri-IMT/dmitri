from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    role: Literal["admin", "viewer"]
