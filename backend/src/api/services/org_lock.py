from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

ORG_ADMIN_LOCK_NAMESPACE = 8818


def lock_org_admins(session: Session, *, org_id: UUID) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:org_id))"),
        {"namespace": ORG_ADMIN_LOCK_NAMESPACE, "org_id": str(org_id)},
    )
