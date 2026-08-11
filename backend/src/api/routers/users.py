from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_admin, require_user_row
from api.errors import ApiError
from api.models.identity import User
from api.schemas.users import (
    OrgMember,
    OrgMemberListResponse,
    UpdateUserRoleRequest,
    UserProfileResponse,
)
from api.services.users import (
    LastAdminError,
    change_member_role,
    delete_member,
    delete_self,
    list_org_members,
)

router = APIRouter()


@router.get("/api/v1/users/me", response_model=UserProfileResponse)
def read_current_user(
    user: User = Depends(require_user_row),
) -> UserProfileResponse:
    return UserProfileResponse(user_id=user.id, email=user.email, role=user.role)


@router.delete("/api/v1/users/me", status_code=204)
def delete_current_user_route(
    user: User = Depends(require_user_row),
    session: Session = Depends(get_session),
) -> None:
    try:
        delete_self(session, user=user)
    except LastAdminError as exc:
        raise ApiError(
            409,
            "Add another admin before removing your account.",
            code="last_admin",
        ) from exc


@router.get("/api/v1/users", response_model=OrgMemberListResponse)
def list_org_users_route(
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> OrgMemberListResponse:
    members = list_org_members(session, org_id=caller.org_id)
    return OrgMemberListResponse(
        data=[
            OrgMember(
                user_id=member.id,
                email=member.email,
                role=member.role,
                last_seen_at=member.last_seen_at,
            )
            for member in members
        ]
    )


@router.patch("/api/v1/users/{user_id}", response_model=OrgMember)
def update_user_role_route(
    user_id: UUID,
    body: UpdateUserRoleRequest,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> OrgMember:
    if user_id == caller.sub:
        raise ApiError(
            409,
            "You cannot change your own role.",
            code="self_target",
        )
    try:
        member = change_member_role(
            session,
            user_id=user_id,
            org_id=caller.org_id,
            role=body.role,
        )
    except LastAdminError as exc:
        raise ApiError(
            409,
            "Add another admin before changing this role.",
            code="last_admin",
        ) from exc
    if member is None:
        raise ApiError(404, "User not found", code="not_found")
    return OrgMember(
        user_id=member.id,
        email=member.email,
        role=member.role,
        last_seen_at=member.last_seen_at,
    )


@router.delete("/api/v1/users/{user_id}", status_code=204)
def delete_user_route(
    user_id: UUID,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    if user_id == caller.sub:
        raise ApiError(
            409,
            "Remove your account from Settings instead.",
            code="self_target",
        )
    if not delete_member(session, user_id=user_id, org_id=caller.org_id):
        raise HTTPException(status_code=404, detail="User not found")
