from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260811_17_agents_target_subnet.py"
    spec = importlib.util.spec_from_file_location("task_1_target_subnet", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()

    assert migration.revision == "20260811_17"
    assert migration.down_revision == "20260810_16"


def test_upgrade_adds_one_nullable_column_and_no_raw_statement(
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
        ("agents", "target_subnet")
    ]
    column = added[0][1]
    assert isinstance(column.type, sa.String)
    assert column.nullable is True
    assert column.index in (None, False)
    assert executed == []


def test_downgrade_drops_only_the_target_subnet_column(
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

    assert events == [("drop_column", "agents", "target_subnet")]


def test_live_target_subnet_column_is_nullable_varchar(
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agents' "
                "AND column_name = 'target_subnet'"
            )
        ).one()

    assert (row.data_type, row.is_nullable) == ("character varying", "YES")


def test_live_target_subnet_column_is_not_indexed(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        indexes = (
            connection.execute(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' AND tablename = 'agents' "
                    "AND indexdef LIKE '%target_subnet%'"
                )
            )
            .scalars()
            .all()
        )

    assert indexes == []


def test_live_agents_table_stores_no_online_or_reported_networks(
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as connection:
        columns = (
            connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'agents'"
                )
            )
            .scalars()
            .all()
        )

    assert "online" not in columns
    assert "available_subnets" not in columns
