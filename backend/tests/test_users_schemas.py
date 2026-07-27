from __future__ import annotations

from uuid import UUID

import pydantic
import pytest
from api.schemas.users import UserProfileResponse


def test_user_profile_response_validates_good_payload():
    user_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    response = UserProfileResponse.model_validate(
        {"user_id": user_id, "email": "a@b.com", "role": "admin"}
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
