from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.models.identity import User
from api.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
)
from api.services.auth import (
    InvalidCredentialsError,
    InvalidResetTokenError,
    WrongCurrentPasswordError,
    change_password,
    forgot_password,
    login,
    logout,
    refresh_session,
    reset_password,
)
from api.services.mailer import LogMailer
from api.services.passwords import PasswordPolicyError
from api.services.tokens import RefreshTokenError
from api.session_response import clear_refresh_cookie, login_response

router = APIRouter()


@router.post("/api/v1/auth/login", response_model=LoginResponse)
def login_route(
    body: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> LoginResponse:
    try:
        access_token, refresh_token, expires_in = login(
            session, email=body.email, password=body.password
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return login_response(response, access_token, refresh_token, expires_in)


@router.post("/api/v1/auth/refresh", response_model=LoginResponse)
def refresh_route(
    response: Response,
    dmitri_refresh: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> LoginResponse:
    if dmitri_refresh is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        access_token, new_refresh_token, expires_in = refresh_session(
            session, refresh_token=dmitri_refresh
        )
    except RefreshTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return login_response(response, access_token, new_refresh_token, expires_in)


@router.post("/api/v1/auth/logout", status_code=204)
def logout_route(
    response: Response,
    dmitri_refresh: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> None:
    if dmitri_refresh is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    logout(session, refresh_token=dmitri_refresh)
    clear_refresh_cookie(response)


@router.post("/api/v1/auth/change-password", status_code=204)
def change_password_route(
    body: ChangePasswordRequest,
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    user = session.get(User, caller.sub)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        change_password(
            session,
            user=user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except (WrongCurrentPasswordError, PasswordPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/auth/forgot-password", status_code=204)
def forgot_password_route(
    body: ForgotPasswordRequest,
    session: Session = Depends(get_session),
) -> None:
    forgot_password(session, email=body.email, mailer=LogMailer())


@router.post("/api/v1/auth/reset-password", status_code=204)
def reset_password_route(
    body: ResetPasswordRequest,
    session: Session = Depends(get_session),
) -> None:
    try:
        reset_password(session, token=body.token, new_password=body.new_password)
    except (InvalidResetTokenError, PasswordPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def auth_preflight() -> None:
    return None


# A real browser preflight is answered by NoContentCorsMiddleware before routing;
# these handlers only serve bare OPTIONS requests. Derived from the POST routes
# above so a new endpoint cannot be added without its preflight.
for _route in list(router.routes):
    if "POST" in _route.methods:
        router.add_api_route(
            _route.path, auth_preflight, methods=["OPTIONS"], status_code=204
        )
