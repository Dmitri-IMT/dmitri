from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import func, nulls_last
from sqlmodel import Session, select

from api.models.identity import ROLE_ADMIN, User
from api.models.persistence import utc_now
from api.services.activity import ActivityAppend, append_activity
from api.services.org_lock import lock_org_admins


class LastAdminError(ValueError):
    pass


def count_org_admins(session: Session, *, org_id: UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(User)
        .where(User.org_id == org_id, User.role == ROLE_ADMIN)
    ).one()


def list_org_members(session: Session, *, org_id: UUID) -> list[User]:
    return session.exec(
        select(User)
        .where(User.org_id == org_id)
        .order_by(nulls_last(User.last_seen_at.desc()), User.id.asc())
    ).all()


def change_member_role(
    session: Session,
    *,
    user_id: UUID,
    org_id: UUID,
    role: Literal["admin", "viewer"],
    actor: User,
) -> User | None:
    lock_org_admins(session, org_id=org_id)
    target = session.exec(
        select(User).where(User.id == user_id, User.org_id == org_id)
    ).first()
    if target is None:
        return None
    if (
        target.role == ROLE_ADMIN
        and role != ROLE_ADMIN
        and count_org_admins(session, org_id=org_id) == 1
    ):
        raise LastAdminError("org would be left without an admin")
    target.role = role
    session.add(target)
    append_activity(
        session,
        ActivityAppend(
            org_id=org_id,
            kind="role_changed",
            occurred_at=utc_now(),
            actor_user_id=actor.id,
            subject_id=target.id,
            payload={
                "actor_email": actor.email,
                "target_email": target.email,
                "new_role": role,
            },
        ),
    )
    session.commit()
    return target


def delete_self(session: Session, *, user: User) -> None:
    if user.role == ROLE_ADMIN and count_org_admins(session, org_id=user.org_id) == 1:
        raise LastAdminError("org would be left without an admin")
    append_activity(
        session,
        ActivityAppend(
            org_id=user.org_id,
            kind="account_deleted",
            occurred_at=utc_now(),
            actor_user_id=user.id,
            subject_id=user.id,
            payload={"email": user.email},
        ),
    )
    session.delete(user)
    session.commit()


def delete_member(
    session: Session,
    *,
    user_id: UUID,
    org_id: UUID,
    actor: User,
) -> bool:
    user = session.exec(
        select(User).where(User.id == user_id, User.org_id == org_id)
    ).first()
    if user is None:
        return False
    append_activity(
        session,
        ActivityAppend(
            org_id=org_id,
            kind="member_removed",
            occurred_at=utc_now(),
            actor_user_id=actor.id,
            subject_id=user.id,
            payload={
                "actor_email": actor.email,
                "target_email": user.email,
            },
        ),
    )
    session.delete(user)
    session.commit()
    return True
