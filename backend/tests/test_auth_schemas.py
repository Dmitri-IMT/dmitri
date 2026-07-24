from __future__ import annotations

import pydantic
import pytest
from api.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
)


def test_login_request_validates_good_payload():
    request = LoginRequest.model_validate({"email": "a@b.com", "password": "x"})

    assert request.email == "a@b.com"
    assert request.password == "x"


def test_login_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        LoginRequest.model_validate(
            {"email": "a@b.com", "password": "x", "remember_me": True}
        )


def test_login_response_accepts_bearer_token_type():
    response = LoginResponse.model_validate(
        {"access_token": "jwt", "token_type": "bearer", "expires_in": 900}
    )

    assert response.token_type == "bearer"


def test_login_response_rejects_non_bearer_token_type():
    with pytest.raises(pydantic.ValidationError):
        LoginResponse.model_validate(
            {"access_token": "jwt", "token_type": "basic", "expires_in": 900}
        )


def test_login_response_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        LoginResponse.model_validate(
            {
                "access_token": "jwt",
                "token_type": "bearer",
                "expires_in": 900,
                "refresh_token": "leaked",
            }
        )


def test_change_password_request_validates_good_payload():
    request = ChangePasswordRequest.model_validate(
        {"current_password": "old-secret", "new_password": "a" * 12}
    )

    assert request.new_password == "a" * 12


def test_change_password_request_rejects_short_new_password():
    with pytest.raises(pydantic.ValidationError):
        ChangePasswordRequest.model_validate(
            {"current_password": "old-secret", "new_password": "a" * 11}
        )


def test_change_password_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        ChangePasswordRequest.model_validate(
            {
                "current_password": "old-secret",
                "new_password": "a" * 12,
                "confirm_password": "a" * 12,
            }
        )


def test_forgot_password_request_validates_good_payload():
    request = ForgotPasswordRequest.model_validate({"email": "a@b.com"})

    assert request.email == "a@b.com"


def test_forgot_password_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        ForgotPasswordRequest.model_validate({"email": "a@b.com", "redirect_url": "https://x"})


def test_reset_password_request_validates_good_payload():
    request = ResetPasswordRequest.model_validate(
        {"token": "tok", "new_password": "a" * 12}
    )

    assert request.new_password == "a" * 12


def test_reset_password_request_rejects_short_new_password():
    with pytest.raises(pydantic.ValidationError):
        ResetPasswordRequest.model_validate({"token": "tok", "new_password": "a" * 11})


def test_reset_password_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        ResetPasswordRequest.model_validate(
            {"token": "tok", "new_password": "a" * 12, "email": "a@b.com"}
        )
