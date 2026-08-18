from __future__ import annotations

from fastapi import Response

from api.core.config import get_settings
from api.schemas.auth import LoginResponse

COOKIE_NAME = "dmitri_refresh"
COOKIE_PATH = "/api/v1/auth"


# The SPA and the API are served from different registrable domains in
# production (`nspi.up.railway.app` vs `api-nspi.up.railway.app`), so a refresh
# call is a cross-site subresource request and a `Lax` cookie would never be
# attached. `None` requires `Secure`, which `refresh_cookie_secure` supplies;
# localhost is exempt from the HTTPS requirement, so local dev is unaffected.
def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        samesite="none",
        secure=settings.refresh_cookie_secure,
        path=COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        samesite="none",
        secure=settings.refresh_cookie_secure,
        path=COOKIE_PATH,
    )


def login_response(
    response: Response, access_token: str, refresh_token: str, expires_in: int
) -> LoginResponse:
    set_refresh_cookie(response, refresh_token)
    return LoginResponse(
        access_token=access_token, token_type="bearer", expires_in=expires_in
    )
