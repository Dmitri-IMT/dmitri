from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, select

from api.core.config import get_settings
from api.models.identity import Invite, Org, User
from api.models.persistence import utc_now
from api.services.auth import issue_session
from api.services.mailer import Mailer
from api.services.passwords import hash_password, validate_policy
from api.services.tokens import hash_token


class InviteTokenError(ValueError):
    pass


class DuplicateUserError(ValueError):
    pass


class AlreadyMemberError(ValueError):
    pass


class PendingInviteError(ValueError):
    pass


INVITE_LOCK_NAMESPACE = 8817


def create_invite(
    session: Session,
    *,
    org_id: UUID,
    email: str,
    role: str,
    mailer: Mailer,
) -> tuple[str, datetime]:
    session.execute(
        text(
            "SELECT pg_advisory_xact_lock(:namespace, hashtext(:org_id || :email))"
        ),
        {
            "namespace": INVITE_LOCK_NAMESPACE,
            "org_id": str(org_id),
            "email": email.lower(),
        },
    )

    existing = session.exec(
        select(User).where(
            func.lower(User.email) == email.lower(), User.org_id == org_id
        )
    ).first()
    if existing is not None:
        raise AlreadyMemberError("email is already a member of this org")

    now = utc_now()
    pending = session.exec(
        select(Invite).where(
            Invite.org_id == org_id,
            func.lower(Invite.email) == email.lower(),
            Invite.consumed_at.is_(None),
            Invite.expires_at > now,
        )
    ).first()
    if pending is not None:
        raise PendingInviteError("email already has a pending invite")

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
    session: Session, *, token: str, password: str
) -> tuple[str, str, int]:
    invite = session.exec(
        select(Invite).where(Invite.token_hash == hash_token(token))
    ).first()
    now = utc_now()
    if invite is None or invite.consumed_at is not None or invite.expires_at <= now:
        raise InviteTokenError("invalid or expired invite token")

    existing = session.exec(
        select(User).where(func.lower(User.email) == invite.email.lower())
    ).first()
    if existing is not None:
        raise DuplicateUserError("email is already registered")

    validate_policy(password, email=invite.email)

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


def read_invite(session: Session, *, token: str) -> tuple[str, str, str]:
    invite = session.exec(
        select(Invite).where(Invite.token_hash == hash_token(token))
    ).first()
    now = utc_now()
    if invite is None or invite.consumed_at is not None or invite.expires_at <= now:
        raise InviteTokenError("invalid or expired invite token")

    org = session.get(Org, invite.org_id)
    return invite.email, invite.role, org.name


def _pending_invite_predicate(
    now: datetime,
) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    return Invite.consumed_at.is_(None), Invite.expires_at > now


def list_pending_invites(session: Session, *, org_id: UUID) -> list[Invite]:
    return session.exec(
        select(Invite)
        .where(
            Invite.org_id == org_id,
            *_pending_invite_predicate(utc_now()),
        )
        .order_by(Invite.expires_at.asc(), Invite.id.asc())
    ).all()


def revoke_invite(session: Session, *, invite_id: UUID, org_id: UUID) -> bool:
    invite = session.exec(
        select(Invite).where(
            Invite.id == invite_id,
            Invite.org_id == org_id,
            *_pending_invite_predicate(utc_now()),
        )
    ).first()
    if invite is None:
        return False
    session.delete(invite)
    session.commit()
    return True
