from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_admin
from api.schemas.auth import LoginResponse
from api.schemas.invites import (
    AcceptInviteRequest,
    CreateInviteRequest,
    InviteCreatedResponse,
)
from api.services.invites import (
    AlreadyMemberError,
    DuplicateUserError,
    InviteEmailMismatchError,
    InviteTokenError,
    accept_invite,
    create_invite,
)
from api.services.mailer import LogMailer
from api.services.passwords import PasswordPolicyError
from api.session_response import login_response

router = APIRouter()


@router.post(
    "/api/v1/invites", response_model=InviteCreatedResponse, status_code=201
)
def create_invite_route(
    body: CreateInviteRequest,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> InviteCreatedResponse:
    try:
        invite_token, expires_at = create_invite(
            session,
            org_id=caller.org_id,
            email=body.email,
            role=body.role,
            mailer=LogMailer(),
        )
    except AlreadyMemberError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InviteCreatedResponse(invite_token=invite_token, expires_at=expires_at)


@router.post("/api/v1/invites/{token}/accept", status_code=201)
def accept_invite_route(
    token: str,
    body: AcceptInviteRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> LoginResponse:
    try:
        access_token, refresh_token, expires_in = accept_invite(
            session, token=token, email=body.email, password=body.password
        )
    except InviteTokenError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except (
        InviteEmailMismatchError,
        DuplicateUserError,
        PasswordPolicyError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return login_response(response, access_token, refresh_token, expires_in)


def invite_preflight() -> None:
    return None


for _route in list(router.routes):
    if "POST" in _route.methods:
        router.add_api_route(
            _route.path, invite_preflight, methods=["OPTIONS"], status_code=204
        )
