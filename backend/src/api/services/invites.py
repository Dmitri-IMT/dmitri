from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.core.config import get_settings
from api.models.identity import Invite, User
from api.models.persistence import utc_now
from api.services.auth import issue_session
from api.services.mailer import Mailer
from api.services.passwords import hash_password, validate_policy
from api.services.tokens import hash_token


class InviteTokenError(ValueError):
    pass


class InviteEmailMismatchError(ValueError):
    pass


class DuplicateUserError(ValueError):
    pass


class AlreadyMemberError(ValueError):
    pass


def create_invite(
    session: Session,
    *,
    org_id: UUID,
    email: str,
    role: str,
    mailer: Mailer,
) -> tuple[str, datetime]:
    existing = session.exec(
        select(User).where(
            func.lower(User.email) == email.lower(), User.org_id == org_id
        )
    ).first()
    if existing is not None:
        raise AlreadyMemberError("email is already a member of this org")

    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(hours=settings.invite_ttl_hours)
    invite = Invite(
        org_id=org_id,
        email=email,
        role=role,
        token_hash=hash_token(raw),
        expires_at=expires_at,
    )
    session.add(invite)
    session.commit()
    mailer.send_invite_link(email, raw)
    return raw, expires_at


def accept_invite(
    session: Session, *, token: str, email: str, password: str
) -> tuple[str, str, int]:
    invite = session.exec(
        select(Invite).where(Invite.token_hash == hash_token(token))
    ).first()
    now = utc_now()
    if invite is None or invite.consumed_at is not None or invite.expires_at <= now:
        raise InviteTokenError("invalid or expired invite token")

    if invite.email.lower() != email.lower():
        raise InviteEmailMismatchError("email does not match the invite")

    existing = session.exec(
        select(User).where(func.lower(User.email) == email.lower())
    ).first()
    if existing is not None:
        raise DuplicateUserError("email is already registered")

    validate_policy(password, email=email)

    user = User(
        org_id=invite.org_id,
        email=invite.email,
        password_hash=hash_password(password),
        role=invite.role,
    )
    session.add(user)
    invite.consumed_at = now
    session.add(invite)
    # The lookup above is only a fast path for a friendly error. A concurrent
    # accept can register the same address between that read and this commit, so
    # the unique index on lower(email) is the real guard; rolling back here also
    # leaves the invite unconsumed and retryable.
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateUserError("email is already registered") from exc
    session.refresh(user)

    return issue_session(session, user=user)
