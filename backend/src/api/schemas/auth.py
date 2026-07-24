from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, constr

from api.services.passwords import MIN_LENGTH


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: constr(min_length=1)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: constr(min_length=MIN_LENGTH)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: constr(min_length=MIN_LENGTH)
