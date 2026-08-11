from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import func, nulls_last
from sqlmodel import Session, select

from api.models.identity import ROLE_ADMIN, User
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
    session.commit()
    return target


def delete_self(session: Session, *, user: User) -> None:
    if user.role == ROLE_ADMIN and count_org_admins(session, org_id=user.org_id) == 1:
        raise LastAdminError("org would be left without an admin")
    session.delete(user)
    session.commit()


def delete_member(session: Session, *, user_id: UUID, org_id: UUID) -> bool:
    user = session.exec(
        select(User).where(User.id == user_id, User.org_id == org_id)
    ).first()
    if user is None:
        return False
    session.delete(user)
    session.commit()
    return True
