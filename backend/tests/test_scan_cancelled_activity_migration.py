from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260927_37_scan_cancelled_activity.py"
    spec = importlib.util.spec_from_file_location("scan_cancelled_activity", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_cancelled_kind_to_check_and_unique_index(
    monkeypatch,
) -> None:
    migration = _load_migration()
    dropped: list[tuple[str, str, dict[str, object]]] = []
    created: list[tuple[str, str, str, dict[str, object]]] = []
    executed: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, **kwargs: dropped.append((name, table, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition, **kwargs: created.append(
            (name, table, condition, kwargs)
        ),
    )
    monkeypatch.setattr(
        migration.op, "execute", lambda statement: executed.append(str(statement))
    )

    migration.upgrade()

    expected_kinds = (
        "scan_started",
        "scan_finished",
        "scan_failed",
        "scan_cancelled",
        "machine_first_seen",
        "role_changed",
        "member_invited",
        "invite_revoked",
        "member_removed",
        "account_deleted",
    )
    expected_unique_kinds = (
        "scan_started",
        "scan_finished",
        "scan_failed",
        "scan_cancelled",
        "machine_first_seen",
        "member_invited",
        "invite_revoked",
    )
    assert migration.KINDS == expected_kinds
    assert migration.UNIQUE_KINDS == expected_unique_kinds
    assert dropped == [
        ("ck_activity_kind", "activity", {"schema": "public", "type_": "check"})
    ]
    assert created == [
        (
            "ck_activity_kind",
            "activity",
            "kind IN (" + ", ".join(f"'{kind}'" for kind in expected_kinds) + ")",
            {"schema": "public"},
        )
    ]
    assert " ".join(executed[1].split()) == (
        "CREATE UNIQUE INDEX uq_activity_org_kind_subject "
        "ON public.activity (org_id, kind, subject_id) "
        "WHERE subject_id IS NOT NULL AND kind IN "
        "('scan_started', 'scan_finished', 'scan_failed', 'scan_cancelled', "
        "'machine_first_seen', 'member_invited', 'invite_revoked')"
    )
    assert executed[0] == "DROP INDEX IF EXISTS public.uq_activity_org_kind_subject"


def test_downgrade_removes_cancelled_rows_and_restores_previous_constraints(
    monkeypatch,
) -> None:
    migration = _load_migration()
    dropped: list[tuple[str, str, dict[str, object]]] = []
    created: list[tuple[str, str, str, dict[str, object]]] = []
    executed: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, **kwargs: dropped.append((name, table, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition, **kwargs: created.append(
            (name, table, condition, kwargs)
        ),
    )
    monkeypatch.setattr(
        migration.op, "execute", lambda statement: executed.append(str(statement))
    )

    migration.downgrade()

    previous_kinds = (
        "scan_started",
        "scan_finished",
        "scan_failed",
        "machine_first_seen",
        "role_changed",
        "member_invited",
        "invite_revoked",
        "member_removed",
        "account_deleted",
    )
    previous_unique_kinds = (
        "scan_started",
        "scan_finished",
        "scan_failed",
        "machine_first_seen",
        "member_invited",
        "invite_revoked",
    )
    assert migration.PREVIOUS_KINDS == previous_kinds
    assert migration.PREVIOUS_UNIQUE_KINDS == previous_unique_kinds
    assert executed[0] == "DELETE FROM public.activity WHERE kind = 'scan_cancelled'"
    assert executed[1] == "DROP INDEX IF EXISTS public.uq_activity_org_kind_subject"
    assert " ".join(executed[2].split()) == (
        "CREATE UNIQUE INDEX uq_activity_org_kind_subject "
        "ON public.activity (org_id, kind, subject_id) "
        "WHERE subject_id IS NOT NULL AND kind IN "
        "('scan_started', 'scan_finished', 'scan_failed', 'machine_first_seen', "
        "'member_invited', 'invite_revoked')"
    )
    assert "scan_cancelled" not in created[0][2]
    assert created == [
        (
            "ck_activity_kind",
            "activity",
            "kind IN (" + ", ".join(f"'{kind}'" for kind in previous_kinds) + ")",
            {"schema": "public"},
        )
    ]
    assert dropped == [
        ("ck_activity_kind", "activity", {"schema": "public", "type_": "check"})
    ]
