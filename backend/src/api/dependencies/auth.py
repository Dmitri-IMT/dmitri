from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlmodel import Session

from api.db.session import get_session
from api.models.identity import ROLE_ADMIN, User
from api.services.tokens import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


class CallerIdentity(BaseModel):
    sub: UUID
    org_id: UUID
    role: str


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CallerIdentity:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    try:
        return CallerIdentity(
            sub=claims["sub"], org_id=claims["org_id"], role=claims["role"]
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_user_row(
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> User:
    # A signed token whose subject no longer has a row is not an authenticated caller:
    # 401, not 404, so the SPA's refresh interceptor treats it as a dead session.
    user = session.get(User, caller.sub)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(
    caller: CallerIdentity = Depends(require_user),
) -> CallerIdentity:
    if caller.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    return caller
