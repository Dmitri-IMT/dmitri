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
    PendingInvite,
    PendingInviteListResponse,
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


def test_pending_invite_validates_exact_public_shape():
    pending = PendingInvite.model_validate(
        {
            "invite_id": "11111111-1111-1111-1111-111111111111",
            "email": "invitee@corp.com",
            "role": "admin",
            "expires_at": "2026-08-12T12:00:00Z",
        }
    )

    assert pending.model_dump(mode="json") == {
        "invite_id": "11111111-1111-1111-1111-111111111111",
        "email": "invitee@corp.com",
        "role": "admin",
        "expires_at": "2026-08-12T12:00:00Z",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "invite_id": "11111111-1111-1111-1111-111111111111",
            "email": "invitee@corp.com",
            "role": "owner",
            "expires_at": "2026-08-12T12:00:00Z",
        },
        {
            "invite_id": "11111111-1111-1111-1111-111111111111",
            "email": "invitee@corp.com",
            "role": "viewer",
            "expires_at": "2026-08-12T12:00:00Z",
            "token_hash": "secret",
        },
        {
            "invite_id": "11111111-1111-1111-1111-111111111111",
            "email": "invitee@corp.com",
            "role": "viewer",
            "expires_at": "2026-08-12T12:00:00Z",
            "invite_token": "secret",
        },
        {
            "invite_id": "11111111-1111-1111-1111-111111111111",
            "email": "invitee@corp.com",
            "role": "viewer",
            "expires_at": "2026-08-12T12:00:00Z",
            "token": "secret",
        },
    ],
)
def test_pending_invite_rejects_bad_role_and_secret_or_extra_fields(payload):
    with pytest.raises(pydantic.ValidationError):
        PendingInvite.model_validate(payload)


def test_pending_invite_list_response_validates_strict_envelope_and_rows():
    payload = {
        "data": [
            {
                "invite_id": "11111111-1111-1111-1111-111111111111",
                "email": "invitee@corp.com",
                "role": "viewer",
                "expires_at": "2026-08-12T12:00:00Z",
            }
        ]
    }

    response = PendingInviteListResponse.model_validate(payload)

    assert response.model_dump(mode="json") == payload
    with pytest.raises(pydantic.ValidationError):
        PendingInviteListResponse.model_validate({**payload, "total": 1})
    with pytest.raises(pydantic.ValidationError):
        PendingInviteListResponse.model_validate(
            {
                "data": [
                    {
                        **payload["data"][0],
                        "token_hash": "must-not-be-published",
                    }
                ]
            }
        )
