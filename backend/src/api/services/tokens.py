from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
from sqlmodel import Session, select

from api.core.config import get_settings
from api.models.persistence import utc_now
from api.models.session import RefreshToken


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_access_token(*, user_id: UUID, org_id: UUID, role: str) -> str:
    settings = get_settings()
    now = utc_now()
    claims = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(
        claims, settings.jwt_signing_secret.get_secret_value(), algorithm="HS256"
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token, settings.jwt_signing_secret.get_secret_value(), algorithms=["HS256"]
    )


def issue_refresh_token(session: Session, *, user_id: UUID) -> str:
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    now = utc_now()
    row = RefreshToken(
        user_id=user_id,
        family_id=uuid4(),
        token_hash=hash_token(raw),
        family_expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
    )
    session.add(row)
    session.commit()
    return raw


class RefreshTokenError(ValueError):
    pass


def _revoke_family(session: Session, family_id: UUID) -> None:
    now = utc_now()
    rows = session.exec(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = now
            session.add(row)
    session.commit()


def rotate_refresh_token(session: Session, *, raw_token: str) -> tuple[UUID, str]:
    token_hash = hash_token(raw_token)
    row = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    if row is None:
        raise RefreshTokenError("invalid refresh token")

    if row.rotated_at is not None or row.revoked_at is not None:
        _revoke_family(session, row.family_id)
        raise RefreshTokenError("refresh token reuse detected")

    now = utc_now()
    if row.family_expires_at <= now:
        raise RefreshTokenError("refresh token family expired")

    row.rotated_at = now
    session.add(row)

    raw = secrets.token_urlsafe(32)
    new_row = RefreshToken(
        user_id=row.user_id,
        family_id=row.family_id,
        token_hash=hash_token(raw),
        family_expires_at=row.family_expires_at,
    )
    session.add(new_row)
    session.commit()
    return row.user_id, raw


def revoke_refresh_token(session: Session, *, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    row = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    if row is None:
        return
    _revoke_family(session, row.family_id)


def revoke_all_refresh_tokens(session: Session, *, user_id: UUID) -> None:
    now = utc_now()
    rows = session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    ).all()
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = now
            session.add(row)
    session.commit()
