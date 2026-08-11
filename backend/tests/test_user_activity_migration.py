from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
ACTIVITY_COLUMNS = ("last_login_at", "last_seen_at")


def _load_migration():
    path = (
        ROOT
        / "alembic/versions/20260810_16_user_activity_and_invite_revoke.py"
    )
    spec = importlib.util.spec_from_file_location("task_1_user_activity", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()

    assert migration.revision == "20260810_16"
    assert migration.down_revision == "20260808_15"


def test_upgrade_adds_nullable_timezone_columns_and_delete_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    added: list[tuple[str, sa.Column]] = []
    executed: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op, "execute", lambda statement: executed.append(str(statement))
    )

    migration.upgrade()

    assert [(table, column.name) for table, column in added] == [
        ("users", "last_login_at"),
        ("users", "last_seen_at"),
    ]
    for _, column in added:
        assert isinstance(column.type, sa.DateTime)
        assert column.type.timezone is True
        assert column.nullable is True
        assert column.index in (None, False)
    assert executed == ["GRANT DELETE ON TABLE public.invites TO dmitri_runtime"]


def test_downgrade_revokes_delete_before_dropping_activity_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    events: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: events.append(("execute", str(statement))),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: events.append(("drop_column", table, column)),
    )

    migration.downgrade()

    assert events == [
        (
            "execute",
            "REVOKE DELETE ON TABLE public.invites FROM dmitri_runtime",
        ),
        ("drop_column", "users", "last_seen_at"),
        ("drop_column", "users", "last_login_at"),
    ]


def test_live_activity_columns_are_nullable_timestamptz(
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' "
                "AND column_name = ANY(:columns)"
            ),
            {"columns": list(ACTIVITY_COLUMNS)},
        ).all()

    column_shapes = {
        row.column_name: (row.data_type, row.is_nullable) for row in rows
    }
    assert column_shapes == {
        "last_login_at": ("timestamp with time zone", "YES"),
        "last_seen_at": ("timestamp with time zone", "YES"),
    }


@pytest.mark.parametrize("column_name", ACTIVITY_COLUMNS)
def test_live_activity_column_is_not_indexed(
    postgres_engine: Engine, column_name: str
) -> None:
    with postgres_engine.connect() as connection:
        indexes = connection.execute(
            sa.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'users' "
                "AND indexdef LIKE :column_pattern"
            ),
            {"column_pattern": f"%{column_name}%"},
        ).scalars().all()

    assert indexes == []
