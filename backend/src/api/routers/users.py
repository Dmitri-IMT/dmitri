from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies.auth import require_user_row
from api.models.identity import User
from api.schemas.users import UserProfileResponse

router = APIRouter()


@router.get("/api/v1/users/me", response_model=UserProfileResponse)
def read_current_user(
    user: User = Depends(require_user_row),
) -> UserProfileResponse:
    return UserProfileResponse(user_id=user.id, email=user.email, role=user.role)
