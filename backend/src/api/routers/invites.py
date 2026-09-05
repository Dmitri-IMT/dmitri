from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_admin
from api.errors import ApiError
from api.models.identity import User
from api.schemas.auth import LoginResponse
from api.schemas.invites import (
    AcceptInviteRequest,
    CreateInviteRequest,
    InviteCreatedResponse,
    InviteLookupRequest,
    InviteLookupResponse,
    PendingInvite,
    PendingInviteListResponse,
)
from api.services.invites import (
    AlreadyMemberError,
    DuplicateUserError,
    InviteTokenError,
    PendingInviteError,
    accept_invite,
    create_invite,
    list_pending_invites,
    read_invite,
    revoke_invite,
)
from api.services.mailer import get_mailer
from api.services.passwords import PasswordPolicyError
from api.session_response import login_response

router = APIRouter()


@router.post(
    "/api/v1/invites", response_model=InviteCreatedResponse, status_code=201
)
def create_invite_route(
    body: CreateInviteRequest,
    background: BackgroundTasks,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> InviteCreatedResponse:
    actor = session.get(User, caller.sub)
    if actor is None:
        raise ApiError(401, "Not authenticated", code="unauthenticated")
    try:
        invite_token, expires_at = create_invite(
            session,
            org_id=caller.org_id,
            email=body.email,
            role=body.role,
            mailer=get_mailer(background),
            actor_user_id=caller.sub,
            actor_email=actor.email,
        )
    except AlreadyMemberError as exc:
        raise ApiError(400, str(exc), code="email_already_member") from exc
    except PendingInviteError as exc:
        raise ApiError(409, str(exc), code="invite_already_pending") from exc
    return InviteCreatedResponse(invite_token=invite_token, expires_at=expires_at)


@router.post("/api/v1/invites/accept", status_code=201)
def accept_invite_route(
    body: AcceptInviteRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> LoginResponse:
    try:
        access_token, refresh_token, expires_in = accept_invite(
            session, token=body.token, password=body.password
        )
    except InviteTokenError as exc:
        raise ApiError(410, str(exc), code="invalid_invite_token") from exc
    except DuplicateUserError as exc:
        raise ApiError(400, str(exc), code="email_already_registered") from exc
    except PasswordPolicyError as exc:
        raise ApiError(400, str(exc), code="password_policy_violation") from exc
    return login_response(response, access_token, refresh_token, expires_in)


@router.post(
    "/api/v1/invites/lookup", response_model=InviteLookupResponse, status_code=200
)
def lookup_invite_route(
    body: InviteLookupRequest,
    session: Session = Depends(get_session),
) -> InviteLookupResponse:
    try:
        email, role, org_name = read_invite(session, token=body.token)
    except InviteTokenError as exc:
        raise ApiError(410, str(exc), code="invalid_invite_token") from exc
    return InviteLookupResponse(email=email, role=role, org_name=org_name)


@router.get("/api/v1/invites", response_model=PendingInviteListResponse)
def list_invites_route(
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> PendingInviteListResponse:
    invites = list_pending_invites(session, org_id=caller.org_id)
    return PendingInviteListResponse(
        data=[
            PendingInvite(
                invite_id=invite.id,
                email=invite.email,
                role=invite.role,
                expires_at=invite.expires_at,
            )
            for invite in invites
        ]
    )


@router.delete("/api/v1/invites/{invite_id}", status_code=204)
def revoke_invite_route(
    invite_id: UUID,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    actor = session.get(User, caller.sub)
    if actor is None:
        raise ApiError(401, "Not authenticated", code="unauthenticated")
    if not revoke_invite(
        session,
        invite_id=invite_id,
        org_id=caller.org_id,
        actor_user_id=caller.sub,
        actor_email=actor.email,
    ):
        raise ApiError(404, "Invite not found", code="not_found")


def invite_preflight() -> None:
    return None


for _route in list(router.routes):
    if "POST" in _route.methods:
        router.add_api_route(
            _route.path, invite_preflight, methods=["OPTIONS"], status_code=204
        )
