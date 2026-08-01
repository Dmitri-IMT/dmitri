from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from api.core.config import Settings
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260731_13_command_delivery.py"
    spec = importlib.util.spec_from_file_location(
        "task_3_command_delivery", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_org(session: Session) -> Org:
    org = Org(name=f"org-{uuid4()}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _seed_agent(session: Session, org_id) -> Agent:
    agent = Agent(
        org_id=org_id,
        display_name=f"agent-{uuid4()}",
        public_key=b"\x01" * 32,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def _seed_scan(session: Session, org_id) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="standard",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260731_13"
    assert migration.down_revision == "20260727_12"


def test_migration_upgrade_alters_scan_id_adds_check_index_and_connected_at(
    monkeypatch,
) -> None:
    migration = _load_migration()
    altered: list[tuple[str, str, bool]] = []
    checks: list[tuple[str, str, str]] = []
    indexes: list[dict[str, object]] = []
    added: list[tuple[str, sa.Column]] = []
    executed: list[str] = []

    class _Bind:
        def execute(self, _query):
            return type("Result", (), {"fetchall": lambda self: []})()

    monkeypatch.setattr(migration.op, "get_bind", lambda: _Bind())
    monkeypatch.setattr(migration.op, "execute", executed.append)
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda table, column, **kwargs: altered.append(
            (table, column, kwargs.get("nullable"))
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, check: checks.append((name, table, check)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table_name, columns, **kwargs: indexes.append(
            {
                "name": name,
                "table": table_name,
                "columns": columns,
                "unique": kwargs.get("unique"),
                "where": kwargs.get("postgresql_where"),
            }
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )

    migration.upgrade()

    assert altered == [("commands", "scan_id", True)]
    assert checks == [
        (
            "ck_commands_scan_id_or_expired",
            "commands",
            "scan_id IS NOT NULL OR status IN ('queued', 'expired')",
        )
    ]
    assert len(indexes) == 1
    index = indexes[0]
    assert index["name"] == "uq_commands_active_agent"
    assert index["table"] == "commands"
    assert index["columns"] == ["agent_id"]
    assert index["unique"] is True
    assert str(index["where"]) == (
        "status IN ('queued', 'delivered', 'running', 'uploading')"
    )
    assert len(added) == 1
    table, column = added[0]
    assert table == "agents"
    assert column.name == "connected_at"
    assert column.nullable is True
    assert column.type.timezone is True

    # Finishes the timestamptz conversion 20260724_08 skipped for these tables.
    assert executed == [
        f"ALTER TABLE public.{retyped_table} ALTER COLUMN {retyped_column} "
        f"TYPE timestamptz USING {retyped_column} AT TIME ZONE 'UTC'"
        for retyped_table, retyped_columns in (
            migration.NAIVE_TIMESTAMP_COLUMNS.items()
        )
        for retyped_column in retyped_columns
    ]
    assert set(migration.NAIVE_TIMESTAMP_COLUMNS) == {"agents", "commands"}


def test_migration_downgrade_reverses_upgrade(monkeypatch) -> None:
    migration = _load_migration()
    dropped_columns: list[tuple[str, str]] = []
    dropped_indexes: list[str] = []
    dropped_checks: list[tuple[str, str, str]] = []
    altered: list[tuple[str, str, bool]] = []
    executed: list[str] = []

    class _Bind:
        def execute(self, _query):
            return type("Result", (), {"fetchall": lambda self: []})()

    monkeypatch.setattr(migration.op, "get_bind", lambda: _Bind())
    monkeypatch.setattr(migration.op, "execute", executed.append)
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped_columns.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, **kwargs: dropped_indexes.append(name),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, type_="check": dropped_checks.append(
            (name, table, type_)
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda table, column, **kwargs: altered.append(
            (table, column, kwargs.get("nullable"))
        ),
    )

    migration.downgrade()

    assert dropped_columns == [("agents", "connected_at")]
    assert dropped_indexes == ["uq_commands_active_agent"]
    assert dropped_checks == [
        ("ck_commands_scan_id_or_expired", "commands", "check")
    ]
    assert altered == [("commands", "scan_id", False)]
    assert executed == [
        f"ALTER TABLE public.{retyped_table} ALTER COLUMN {retyped_column} "
        f"TYPE timestamp USING {retyped_column} AT TIME ZONE 'UTC'"
        for retyped_table, retyped_columns in (
            migration.NAIVE_TIMESTAMP_COLUMNS.items()
        )
        for retyped_column in retyped_columns
    ]


def test_command_settings_defaults_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.delenv("COMMAND_DISCONNECT_GRACE_SECONDS", raising=False)

    settings = Settings()

    assert settings.command_disconnect_grace_seconds == 900


def test_command_settings_read_from_env_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("COMMAND_DISCONNECT_GRACE_SECONDS", "1200")

    settings = Settings()

    assert settings.command_disconnect_grace_seconds == 1200


@pytest.mark.parametrize("status", ["delivered", "running", "uploading", "done"])
def test_check_rejects_post_delivery_command_with_null_scan_id(
    migrated_database: Engine, status: str
) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)
        session.add(
            Command(
                org_id=org.id,
                agent_id=agent.id,
                scan_id=None,
                scan_mode="standard",
                subnet="192.168.1.0/24",
                status=status,
            )
        )
        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            session.commit()
        assert "ck_commands_scan_id_or_expired" in str(excinfo.value)


def test_queued_command_allows_null_scan_id(migrated_database: Engine) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)
        command = Command(
            org_id=org.id,
            agent_id=agent.id,
            scan_id=None,
            scan_mode="standard",
            subnet="192.168.1.0/24",
            status="queued",
        )
        session.add(command)
        session.commit()
        session.refresh(command)
        assert command.scan_id is None


def test_expired_command_allows_null_scan_id(migrated_database: Engine) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)
        command = Command(
            org_id=org.id,
            agent_id=agent.id,
            scan_id=None,
            scan_mode="standard",
            subnet="192.168.1.0/24",
            status="expired",
        )
        session.add(command)
        session.commit()
        session.refresh(command)
        assert command.scan_id is None


def test_active_command_index_rejects_second_non_terminal_command(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)
        scan_a = _seed_scan(session, org.id)
        scan_b = _seed_scan(session, org.id)

        session.add(
            Command(
                org_id=org.id,
                agent_id=agent.id,
                scan_id=scan_a.scan_id,
                scan_mode="standard",
                subnet="192.168.1.0/24",
                status="queued",
            )
        )
        session.commit()

        session.add(
            Command(
                org_id=org.id,
                agent_id=agent.id,
                scan_id=scan_b.scan_id,
                scan_mode="standard",
                subnet="192.168.1.0/24",
                status="delivered",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_active_command_index_permits_new_command_after_terminal(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)
        scan_a = _seed_scan(session, org.id)
        scan_b = _seed_scan(session, org.id)

        first = Command(
            org_id=org.id,
            agent_id=agent.id,
            scan_id=scan_a.scan_id,
            scan_mode="standard",
            subnet="192.168.1.0/24",
            status="done",
        )
        session.add(first)
        session.commit()

        second = Command(
            org_id=org.id,
            agent_id=agent.id,
            scan_id=scan_b.scan_id,
            scan_mode="standard",
            subnet="192.168.1.0/24",
            status="queued",
        )
        session.add(second)
        session.commit()


def test_agents_connected_at_exists_and_defaults_to_null(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)
        assert agent.connected_at is None

    with migrated_database.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agents' "
                "AND column_name = 'connected_at'"
            )
        ).one()
        assert row[0] == "YES"


def test_live_migration_round_trip(migrated_database: Engine) -> None:
    engine = migrated_database
    _migrate(engine, "20260727_12")
    with engine.connect() as connection:
        scan_id_nullable = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'commands' "
                "AND column_name = 'scan_id'"
            )
        ).scalar_one()
        assert scan_id_nullable == "NO"
        connected_at_exists = connection.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agents' "
                "AND column_name = 'connected_at'"
            )
        ).fetchone()
        assert connected_at_exists is None

    _migrate(engine, "head")
    with engine.connect() as connection:
        scan_id_nullable = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'commands' "
                "AND column_name = 'scan_id'"
            )
        ).scalar_one()
        assert scan_id_nullable == "YES"
        check = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = 'ck_commands_scan_id_or_expired'"
            )
        ).fetchone()
        assert check is not None
        index = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes "
                "WHERE indexname = 'uq_commands_active_agent'"
            )
        ).fetchone()
        assert index is not None
        connected_at_exists = connection.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agents' "
                "AND column_name = 'connected_at'"
            )
        ).fetchone()
        assert connected_at_exists is not None

    _migrate(engine, "20260727_12")
    with engine.connect() as connection:
        scan_id_nullable = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'commands' "
                "AND column_name = 'scan_id'"
            )
        ).scalar_one()
        assert scan_id_nullable == "NO"
        check = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = 'ck_commands_scan_id_or_expired'"
            )
        ).fetchone()
        assert check is None
        index = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes "
                "WHERE indexname = 'uq_commands_active_agent'"
            )
        ).fetchone()
        assert index is None
        connected_at_exists = connection.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agents' "
                "AND column_name = 'connected_at'"
            )
        ).fetchone()
        assert connected_at_exists is None

    _migrate(engine, "head")
