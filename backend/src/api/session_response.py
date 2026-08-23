from __future__ import annotations

from fastapi import Response

from api.core.config import get_settings
from api.schemas.auth import LoginResponse

COOKIE_NAME = "dmitri_refresh"
COOKIE_PATH = "/api/v1/auth"


# The SPA and the API are served from the same registrable domain in production
# (`dmitri.peirce.dev` and `api.peirce.dev`), so a refresh call is same-site and
# a `Lax` cookie is attached to it. `Lax` was briefly `None` (2026-08-18,
# `f2836ba`), while both services still sat under the public suffix
# `up.railway.app` and were therefore cross-site.
def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.refresh_cookie_secure,
        path=COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        samesite="lax",
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
