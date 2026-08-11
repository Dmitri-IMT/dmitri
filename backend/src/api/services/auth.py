from __future__ import annotations

import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, update
from sqlmodel import Session, select

from api.core.config import get_settings
from api.models.identity import User
from api.models.persistence import utc_now
from api.models.session import PasswordResetToken
from api.services.mailer import Mailer
from api.services.passwords import hash_password, validate_policy, verify_password
from api.services.tokens import (
    RefreshTokenError,
    create_access_token,
    hash_token,
    issue_refresh_token,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)


class InvalidCredentialsError(ValueError):
    pass


class WrongCurrentPasswordError(ValueError):
    pass


class InvalidResetTokenError(ValueError):
    pass


def _stamp_activity(session: Session, *, user_id: UUID, login: bool) -> None:
    now = utc_now()
    values = {"last_seen_at": now}
    if login:
        values["last_login_at"] = now
    session.execute(update(User).where(User.id == user_id).values(**values))
    # Committed here rather than by the caller: activity is a standalone fact,
    # and every call site would otherwise have to remember to flush it.
    session.commit()


def issue_session(session: Session, *, user: User) -> tuple[str, str, int]:
    settings = get_settings()
    user_id = user.id
    access_token = create_access_token(
        user_id=user_id, org_id=user.org_id, role=user.role
    )
    _stamp_activity(session, user_id=user_id, login=True)
    refresh_token = issue_refresh_token(session, user_id=user_id)
    return access_token, refresh_token, settings.access_token_ttl_minutes * 60


def login(session: Session, *, email: str, password: str) -> tuple[str, str, int]:
    user = session.exec(
        select(User).where(func.lower(User.email) == email.lower())
    ).first()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("invalid email or password")
    return issue_session(session, user=user)


def refresh_session(
    session: Session, *, refresh_token: str
) -> tuple[str, str, int]:
    user_id, new_refresh_token = rotate_refresh_token(
        session, raw_token=refresh_token
    )
    user = session.get(User, user_id)
    if user is None:
        raise RefreshTokenError("invalid refresh token")
    settings = get_settings()
    access_token = create_access_token(
        user_id=user.id, org_id=user.org_id, role=user.role
    )
    _stamp_activity(session, user_id=user_id, login=False)
    return access_token, new_refresh_token, settings.access_token_ttl_minutes * 60


def logout(session: Session, *, refresh_token: str) -> None:
    revoke_refresh_token(session, raw_token=refresh_token)


def change_password(
    session: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise WrongCurrentPasswordError("current password is incorrect")
    validate_policy(new_password, email=user.email)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = utc_now()
    session.add(user)
    session.commit()


def forgot_password(session: Session, *, email: str, mailer: Mailer) -> None:
    settings = get_settings()
    user = session.exec(
        select(User).where(func.lower(User.email) == email.lower())
    ).first()
    if user is None:
        return
    raw = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=utc_now()
        + timedelta(minutes=settings.reset_token_ttl_minutes),
    )
    session.add(row)
    session.commit()
    mailer.send_reset_link(user.email, raw)


def reset_password(session: Session, *, token: str, new_password: str) -> None:
    token_hash = hash_token(token)
    row = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    ).first()
    now = utc_now()
    if row is None or row.consumed_at is not None or row.expires_at <= now:
        raise InvalidResetTokenError("invalid or expired reset token")
    user = session.get(User, row.user_id)
    if user is None:
        raise InvalidResetTokenError("invalid or expired reset token")
    validate_policy(new_password, email=user.email)
    row.consumed_at = now
    session.add(row)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    session.add(user)
    session.commit()
    revoke_all_refresh_tokens(session, user_id=user.id)
