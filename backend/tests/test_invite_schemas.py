from __future__ import annotations

import importlib

import pydantic
import pytest
from api.schemas.invites import (
    AcceptInviteRequest,
    CreateInviteRequest,
    InviteCreatedResponse,
    InviteLookupRequest,
    InviteLookupResponse,
)


def test_create_invite_request_validates_good_payload():
    request = CreateInviteRequest.model_validate({"email": "a@b.com", "role": "admin"})

    assert request.email == "a@b.com"
    assert request.role == "admin"


def test_create_invite_request_rejects_bad_role():
    with pytest.raises(pydantic.ValidationError):
        CreateInviteRequest.model_validate({"email": "a@b.com", "role": "owner"})


def test_create_invite_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        CreateInviteRequest.model_validate(
            {"email": "a@b.com", "role": "admin", "org_id": "some-org"}
        )


def test_invite_created_response_validates_good_payload():
    response = InviteCreatedResponse.model_validate(
        {"invite_token": "tok", "expires_at": "2026-07-24T00:00:00Z"}
    )

    assert response.invite_token == "tok"


def test_invite_created_response_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        InviteCreatedResponse.model_validate(
            {
                "invite_token": "tok",
                "expires_at": "2026-07-24T00:00:00Z",
                "org_id": "some-org",
            }
        )


def test_accept_invite_request_validates_good_payload():
    request = AcceptInviteRequest.model_validate(
        {"token": "test-invite-token", "password": "a" * 12}
    )

    assert request.password == "a" * 12


def test_accept_invite_request_requires_token():
    with pytest.raises(pydantic.ValidationError):
        AcceptInviteRequest.model_validate({"password": "a" * 12})


def test_accept_invite_request_rejects_short_password():
    with pytest.raises(pydantic.ValidationError):
        AcceptInviteRequest.model_validate(
            {"token": "test-invite-token", "password": "a" * 11}
        )


def test_accept_invite_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        AcceptInviteRequest.model_validate(
            {
                "token": "test-invite-token",
                "password": "a" * 12,
                "org_id": "some-org",
            }
        )


def test_accept_invite_request_rejects_email():
    with pytest.raises(pydantic.ValidationError):
        AcceptInviteRequest.model_validate(
            {"token": "test-invite-token", "email": "a@b.com", "password": "a" * 12}
        )


def test_invite_lookup_request_validates_good_payload():
    request = InviteLookupRequest.model_validate({"token": "test-invite-token"})

    assert request.token == "test-invite-token"


def test_invite_lookup_request_requires_token():
    with pytest.raises(pydantic.ValidationError):
        InviteLookupRequest.model_validate({})


def test_invite_lookup_request_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        InviteLookupRequest.model_validate(
            {"token": "test-invite-token", "role": "admin"}
        )


def test_invite_lookup_response_validates_good_payload():
    response = InviteLookupResponse.model_validate(
        {"email": "a@b.com", "role": "viewer", "org_name": "Acme"}
    )

    assert response.email == "a@b.com"
    assert response.role == "viewer"
    assert response.org_name == "Acme"


def test_invite_lookup_response_rejects_bad_role():
    with pytest.raises(pydantic.ValidationError):
        InviteLookupResponse.model_validate(
            {"email": "a@b.com", "role": "owner", "org_name": "Acme"}
        )


def test_invite_lookup_response_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        InviteLookupResponse.model_validate(
            {
                "email": "a@b.com",
                "role": "admin",
                "org_name": "Acme",
                "org_id": "some-org",
            }
        )


def test_accept_invite_request_password_min_length_tracks_constant(monkeypatch):
    import api.schemas.invites as invites_module
    import api.services.passwords as passwords_module

    monkeypatch.setattr(passwords_module, "MIN_LENGTH", 20)
    reloaded = importlib.reload(invites_module)
    try:
        with pytest.raises(pydantic.ValidationError):
            reloaded.AcceptInviteRequest.model_validate(
                {"token": "test-invite-token", "password": "a" * 19}
            )
        reloaded.AcceptInviteRequest.model_validate(
            {"token": "test-invite-token", "password": "a" * 20}
        )
    finally:
        monkeypatch.undo()
        restored = importlib.reload(invites_module)

    with pytest.raises(pydantic.ValidationError):
        restored.AcceptInviteRequest.model_validate(
            {"token": "test-invite-token", "password": "a" * 11}
        )
    restored.AcceptInviteRequest.model_validate(
        {"token": "test-invite-token", "password": "a" * 12}
    )
