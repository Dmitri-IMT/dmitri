from __future__ import annotations

from uuid import UUID

import pydantic
import pytest
from api.schemas.users import (
    OrgMember,
    OrgMemberListResponse,
    UpdateUserRoleRequest,
    UserProfileResponse,
)


def test_user_profile_response_validates_good_payload():
    user_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    response = UserProfileResponse.model_validate(
        {"user_id": user_id, "email": "a@b.com", "role": "admin", "org_name": "Acme"}
    )

    assert response.user_id == user_id
    assert response.email == "a@b.com"
    assert response.role == "admin"


def test_user_profile_response_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        UserProfileResponse.model_validate(
            {
                "user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "email": "a@b.com",
                "role": "admin",
                "display_name": "Alice",
            }
        )


def test_user_profile_response_rejects_missing_required_field():
    with pytest.raises(pydantic.ValidationError):
        UserProfileResponse.model_validate(
            {"user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "email": "a@b.com"}
        )


def test_user_profile_response_rejects_invalid_role():
    with pytest.raises(pydantic.ValidationError):
        UserProfileResponse.model_validate(
            {
                "user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "email": "a@b.com",
                "role": "superuser",
            }
        )


@pytest.mark.parametrize("last_seen_at", [None, "2026-08-10T12:00:00Z"])
def test_org_member_validates_exact_shape_and_nullable_last_seen_at(last_seen_at):
    user_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    member = OrgMember.model_validate(
        {
            "user_id": user_id,
            "email": "member@corp.com",
            "role": "viewer",
            "last_seen_at": last_seen_at,
        }
    )

    assert member.user_id == user_id
    assert member.email == "member@corp.com"
    assert member.role == "viewer"
    if last_seen_at is None:
        assert member.last_seen_at is None
    else:
        assert member.last_seen_at is not None


def test_org_member_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        OrgMember.model_validate(
            {
                "user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "email": "member@corp.com",
                "role": "viewer",
                "last_seen_at": None,
                "status": "active",
            }
        )


def test_org_member_rejects_unknown_role():
    with pytest.raises(pydantic.ValidationError):
        OrgMember.model_validate(
            {
                "user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "email": "member@corp.com",
                "role": "owner",
                "last_seen_at": None,
            }
        )


def test_org_member_list_response_validates_members_and_forbids_extra_fields():
    response = OrgMemberListResponse.model_validate(
        {
            "data": [
                {
                    "user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "email": "member@corp.com",
                    "role": "admin",
                    "last_seen_at": None,
                }
            ]
        }
    )

    assert len(response.data) == 1
    assert response.data[0].last_seen_at is None
    with pytest.raises(pydantic.ValidationError):
        OrgMemberListResponse.model_validate({"data": [], "status": "ok"})


@pytest.mark.parametrize("role", ["admin", "viewer"])
def test_update_user_role_request_accepts_only_published_roles(role):
    request = UpdateUserRoleRequest.model_validate({"role": role})

    assert request.role == role


def test_update_user_role_request_rejects_unknown_role():
    with pytest.raises(pydantic.ValidationError):
        UpdateUserRoleRequest.model_validate({"role": "owner"})


def test_update_user_role_request_forbids_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        UpdateUserRoleRequest.model_validate(
            {"role": "viewer", "email": "member@corp.com"}
        )
