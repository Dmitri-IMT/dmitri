from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from api.models.activity import ActivityRecord
from api.models.identity import Org
from api.models.persistence import utc_now
from api.services.activity import (
    ActivityAppend,
    activity_text,
    append_activity,
    append_scan_activity,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select


def _append(
    session: Session,
    org_id: UUID,
    *,
    kind: str,
    subject_id: UUID | None,
    payload: dict[str, str] | None = None,
) -> None:
    append_activity(
        session,
        ActivityAppend(
            org_id=org_id,
            kind=kind,
            occurred_at=utc_now(),
            actor_user_id=None,
            subject_id=subject_id,
            payload=payload or {},
        ),
    )


def _rows(session: Session, org_id: UUID, kind: str) -> list[ActivityRecord]:
    return list(
        session.exec(
            select(ActivityRecord).where(
                ActivityRecord.org_id == org_id, ActivityRecord.kind == kind
            )
        ).all()
    )


def test_duplicate_append_on_guarded_kind_is_a_silent_no_op(
    administrative_session: Session, seeded_org: Org
) -> None:
    subject = uuid4()
    _append(
        administrative_session,
        seeded_org.id,
        kind="scan_started",
        subject_id=subject,
        payload={"scan_mode": "quick"},
    )
    _append(
        administrative_session,
        seeded_org.id,
        kind="scan_started",
        subject_id=subject,
        payload={"scan_mode": "quick"},
    )
    administrative_session.commit()

    assert len(_rows(administrative_session, seeded_org.id, "scan_started")) == 1


@pytest.mark.parametrize(
    "kind", ["role_changed", "member_removed", "account_deleted"]
)
def test_unguarded_kinds_persist_twice_for_one_subject(
    administrative_session: Session, seeded_org: Org, kind: str
) -> None:
    subject = uuid4()
    _append(administrative_session, seeded_org.id, kind=kind, subject_id=subject)
    _append(administrative_session, seeded_org.id, kind=kind, subject_id=subject)
    administrative_session.commit()

    assert len(_rows(administrative_session, seeded_org.id, kind)) == 2


def test_append_does_not_commit(
    administrative_session: Session, seeded_org: Org
) -> None:
    _append(
        administrative_session,
        seeded_org.id,
        kind="scan_finished",
        subject_id=uuid4(),
        payload={"scan_mode": "standard"},
    )
    administrative_session.rollback()

    assert _rows(administrative_session, seeded_org.id, "scan_finished") == []


MATRIX = [
    (
        "scan_started",
        {"scan_mode": "quick"},
        "Quick scan started",
        "Quick scan started",
    ),
    (
        "scan_finished",
        {"scan_mode": "standard"},
        "Standard scan finished",
        "Standard scan finished",
    ),
    (
        "scan_failed",
        {"scan_mode": "nspi"},
        "NSPi scan didn't finish",
        "NSPi scan didn't finish",
    ),
    (
        "machine_first_seen",
        {"hostname": "printer-01"},
        "printer-01 first seen on the network",
        "printer-01 first seen on the network",
    ),
    (
        "role_changed",
        {
            "actor_email": "ada@corp.com",
            "target_email": "bob@corp.com",
            "new_role": "viewer",
        },
        "ada@corp.com changed bob@corp.com's role to viewer",
        "bob@corp.com is now a viewer",
    ),
    (
        "role_changed",
        {
            "actor_email": "ada@corp.com",
            "target_email": "bob@corp.com",
            "new_role": "admin",
        },
        "ada@corp.com changed bob@corp.com's role to admin",
        "bob@corp.com is now an admin",
    ),
    (
        "member_invited",
        {
            "actor_email": "ada@corp.com",
            "invite_email": "new@corp.com",
            "role": "viewer",
        },
        "ada@corp.com invited new@corp.com",
        "new@corp.com was invited",
    ),
    (
        "invite_revoked",
        {"actor_email": "ada@corp.com", "invite_email": "new@corp.com"},
        "ada@corp.com withdrew the invitation for new@corp.com",
        "new@corp.com's invitation is no longer outstanding",
    ),
    (
        "member_removed",
        {"actor_email": "ada@corp.com", "target_email": "bob@corp.com"},
        "ada@corp.com removed bob@corp.com",
        "bob@corp.com is no longer a member",
    ),
    (
        "account_deleted",
        {"email": "bob@corp.com"},
        "bob@corp.com deleted their account",
        "bob@corp.com deleted their account",
    ),
]


@pytest.mark.parametrize(
    "kind,payload,admin,viewer",
    MATRIX,
    ids=[row[0] for row in MATRIX],
)
def test_activity_text_matrix(
    kind: str, payload: dict[str, str], admin: str, viewer: str
) -> None:
    assert activity_text(kind, "admin", payload) == admin
    assert activity_text(kind, "viewer", payload) == viewer


@pytest.mark.parametrize(
    "kind,payload",
    [
        (kind, payload)
        for kind, payload, _admin, _viewer in MATRIX
        if kind
        in {"role_changed", "member_invited", "invite_revoked", "member_removed"}
    ],
)
def test_viewer_text_names_no_admin_action(
    kind: str, payload: dict[str, str]
) -> None:
    text = activity_text(kind, "viewer", payload)

    assert "invited " not in text
    assert "changed" not in text
    assert "removed" not in text
    assert "withdrew" not in text
    assert payload.get("actor_email", "ada@corp.com") not in text


@pytest.mark.parametrize(
    "kind,payload",
    [
        (kind, payload)
        for kind, payload, _admin, _viewer in MATRIX
        if kind.startswith("scan_") or kind == "machine_first_seen"
    ],
)
def test_box_caused_text_is_role_independent(
    kind: str, payload: dict[str, str]
) -> None:
    assert activity_text(kind, "admin", payload) == activity_text(
        kind, "viewer", payload
    )


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        activity_text("nope", "admin", {})


def test_append_scan_activity_logs_and_continues_on_failure(
    administrative_session: Session,
    seeded_org: Org,
    monkeypatch,
    caplog,
) -> None:
    def fail_activity(*_args, **_kwargs) -> None:
        raise SQLAlchemyError("activity insert failed")

    monkeypatch.setattr(
        "api.services.activity.append_activity",
        fail_activity,
    )

    append_scan_activity(
        administrative_session,
        org_id=seeded_org.id,
        scan_id=uuid4(),
        kind="scan_started",
        scan_mode="quick",
        occurred_at=utc_now(),
    )

    assert "Failed to append scan activity" in caplog.text
    assert _rows(administrative_session, seeded_org.id, "scan_started") == []
