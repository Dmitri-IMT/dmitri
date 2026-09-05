from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from api.models.activity import ActivityKind, ActivityRecord

SCAN_MODE_LABEL = {
    "quick": "Quick",
    "standard": "Standard",
    "extensive": "Extensive",
    "nspi": "NSPi",
    "max": "Max",
}

_SCAN_VERB = {
    "scan_started": "started",
    "scan_finished": "finished",
    "scan_failed": "didn't finish",
}


@dataclass(frozen=True)
class ActivityAppend:
    org_id: UUID
    kind: ActivityKind
    occurred_at: datetime
    actor_user_id: UUID | None
    subject_id: UUID | None
    payload: dict[str, str]


def append_activity(session: Session, row: ActivityAppend) -> None:
    session.execute(
        insert(ActivityRecord.__table__)
        .values(**asdict(row))
        .on_conflict_do_nothing()
    )


def activity_text(kind: str, role: str, payload: dict[str, str]) -> str:
    actor = payload.get("actor_email", "")
    admin = role == "admin"

    if kind in _SCAN_VERB:
        mode = payload.get("scan_mode", "")
        return f"{SCAN_MODE_LABEL.get(mode, mode.capitalize())} scan {_SCAN_VERB[kind]}"
    if kind == "machine_first_seen":
        return f"{payload.get('hostname', '')} first seen on the network"
    if kind == "role_changed":
        target = payload.get("target_email", "")
        new_role = payload.get("new_role", "")
        if admin:
            return f"{actor} changed {target}'s role to {new_role}"
        article = "an" if new_role == "admin" else "a"
        return f"{target} is now {article} {new_role}"
    if kind == "member_invited":
        email = payload.get("invite_email", "")
        return f"{actor} invited {email}" if admin else f"{email} was invited"
    if kind == "invite_revoked":
        email = payload.get("invite_email", "")
        if admin:
            return f"{actor} withdrew the invitation for {email}"
        return f"{email}'s invitation is no longer outstanding"
    if kind == "member_removed":
        target = payload.get("target_email", "")
        if admin:
            return f"{actor} removed {target}"
        return f"{target} is no longer a member"
    if kind == "account_deleted":
        return f"{payload.get('email', '')} deleted their account"
    raise ValueError(f"unknown activity kind: {kind}")
