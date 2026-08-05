from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import ScanRecord
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session
from test_migrations import _has_privilege, _load_baseline, _table_shape

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260804_14_scan_ingest_rework.py"
    spec = importlib.util.spec_from_file_location(
        "task_2_scan_ingest_rework", path
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


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260804_14"
    assert migration.down_revision == "20260731_13"


def test_migration_upgrade_adds_agent_id_and_drops_artifacts(monkeypatch) -> None:
    migration = _load_migration()
    added: list[tuple[str, sa.Column]] = []
    dropped_tables: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op, "drop_table", lambda table: dropped_tables.append(table)
    )

    migration.upgrade()

    assert len(added) == 1
    table, column = added[0]
    assert table == "scans"
    assert column.name == "agent_id"
    assert column.nullable is True
    assert isinstance(column.type, sa.Uuid)
    assert dropped_tables == ["artifacts"]


def test_migration_downgrade_recreates_artifacts_and_drops_agent_id(
    monkeypatch,
) -> None:
    migration = _load_migration()
    created_tables: list[str] = []
    created_indexes: list[tuple[str, str, list[str], bool]] = []
    dropped_columns: list[tuple[str, str]] = []
    statements: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *elements: created_tables.append(name),
    )
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table_name, columns, **kwargs: created_indexes.append(
            (name, table_name, columns, kwargs.get("unique"))
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped_columns.append((table, column)),
    )

    migration.downgrade()

    assert created_tables == ["artifacts"]
    assert created_indexes == [
        ("ix_artifacts_scan_id", "artifacts", ["scan_id"], False)
    ]
    assert dropped_columns == [("scans", "agent_id")]

    joined = "\n".join(statements)
    assert "ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY" in joined
    assert "REVOKE ALL PRIVILEGES ON TABLE public.artifacts FROM anon" in joined
    assert (
        "REVOKE ALL PRIVILEGES ON TABLE public.artifacts FROM authenticated" in joined
    )
    assert "GRANT SELECT, INSERT, UPDATE ON artifacts TO dmitri_runtime" in joined
    assert (
        "GRANT USAGE, SELECT ON SEQUENCE artifacts_id_seq TO dmitri_runtime" in joined
    )


def test_migration_downgrade_recreates_artifacts_matching_baseline(
    monkeypatch,
) -> None:
    migration = _load_migration()
    baseline = _load_baseline()

    baseline_metadata = sa.MetaData()
    baseline_tables: dict[str, sa.Table] = {}
    baseline_indexes: list[tuple[str, str, list[str], bool]] = []
    monkeypatch.setattr(
        baseline.op,
        "create_table",
        lambda name, *elements: baseline_tables.__setitem__(
            name, sa.Table(name, baseline_metadata, *elements)
        ),
    )
    monkeypatch.setattr(
        baseline.op,
        "create_index",
        lambda name, table_name, columns, **kwargs: baseline_indexes.append(
            (name, table_name, columns, kwargs.get("unique"))
        ),
    )
    monkeypatch.setattr(baseline.op, "execute", lambda sql: None)
    baseline.upgrade()

    for name, table_name, columns, unique in baseline_indexes:
        if table_name != "artifacts":
            continue
        sa.Index(
            name,
            *(baseline_tables[table_name].c[column] for column in columns),
            unique=unique,
        )

    downgrade_metadata = sa.MetaData()
    downgrade_tables: dict[str, sa.Table] = {}
    downgrade_indexes: list[tuple[str, str, list[str], bool]] = []
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *elements: downgrade_tables.__setitem__(
            name, sa.Table(name, downgrade_metadata, *elements)
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table_name, columns, **kwargs: downgrade_indexes.append(
            (name, table_name, columns, kwargs.get("unique"))
        ),
    )
    monkeypatch.setattr(migration.op, "drop_column", lambda table, column: None)
    migration.downgrade()

    for name, table_name, columns, unique in downgrade_indexes:
        sa.Index(
            name,
            *(downgrade_tables[table_name].c[column] for column in columns),
            unique=unique,
        )

    assert _table_shape(downgrade_tables["artifacts"]) == _table_shape(
        baseline_tables["artifacts"]
    )


def test_live_migration_round_trip_preserves_scan_data(
    migrated_database: Engine,
) -> None:
    engine = migrated_database
    scan_id = uuid4()

    _migrate(engine, "20260731_13")
    with engine.connect() as connection:
        scans_columns_before = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'scans'"
                )
            )
        }
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO scans "
                "(scan_id, timestamp, subnet, scan_mode, status, created_at) "
                "VALUES (:scan_id, :timestamp, :subnet, :scan_mode, :status, "
                ":created_at)"
            ),
            {
                "scan_id": scan_id,
                "timestamp": datetime.now(timezone.utc),
                "subnet": "192.168.1.0/24",
                "scan_mode": "standard",
                "status": "completed",
                "created_at": datetime.now(timezone.utc),
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO artifacts (scan_id, kind, path, stage) "
                "VALUES (:scan_id, :kind, :path, :stage)"
            ),
            {"scan_id": scan_id, "kind": "log", "path": "/tmp/x", "stage": "scan"},
        )

    _migrate(engine, "head")
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names(schema="public"))
        assert "artifacts" not in tables
        agent_id_column = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'scans' "
                "AND column_name = 'agent_id'"
            )
        ).scalar_one()
        assert agent_id_column == "YES"
        row = connection.execute(
            sa.text(
                "SELECT subnet, scan_mode, status, agent_id FROM scans "
                "WHERE scan_id = :scan_id"
            ),
            {"scan_id": scan_id},
        ).one()
        assert row.subnet == "192.168.1.0/24"
        assert row.scan_mode == "standard"
        assert row.status == "completed"
        assert row.agent_id is None

    _migrate(engine, "20260731_13")
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names(schema="public"))
        assert "artifacts" in tables
        columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'scans'"
                )
            )
        }
        assert "agent_id" not in columns
        assert columns == scans_columns_before
        row = connection.execute(
            sa.text(
                "SELECT subnet, scan_mode, status FROM scans WHERE scan_id = :scan_id"
            ),
            {"scan_id": scan_id},
        ).one()
        assert row.subnet == "192.168.1.0/24"
        assert row.scan_mode == "standard"
        assert row.status == "completed"

    _migrate(engine, "head")
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names(schema="public"))
        assert "artifacts" not in tables
        row = connection.execute(
            sa.text(
                "SELECT subnet, scan_mode, status, agent_id FROM scans "
                "WHERE scan_id = :scan_id"
            ),
            {"scan_id": scan_id},
        ).one()
        assert row.subnet == "192.168.1.0/24"
        assert row.scan_mode == "standard"
        assert row.status == "completed"
        assert row.agent_id is None


def test_downgrade_restores_artifacts_security_fence(
    migrated_database: Engine,
) -> None:
    engine = migrated_database

    _migrate(engine, "20260731_13")
    with engine.connect() as connection:
        rls = connection.execute(
            sa.text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "JOIN pg_namespace ON pg_namespace.oid = relnamespace "
                "WHERE nspname = 'public' AND relname = 'artifacts'"
            )
        ).one()
        assert rls.relrowsecurity is True
        assert rls.relforcerowsecurity is False

        policies = connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = 'artifacts'"
            )
        ).scalar_one()
        assert policies == 0

        for api_role in ("anon", "authenticated"):
            for privilege in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
            ):
                assert not _has_privilege(
                    connection, api_role, "public.artifacts", privilege
                )
            for privilege in ("SELECT", "UPDATE", "USAGE"):
                assert not _has_privilege(
                    connection,
                    api_role,
                    "public.artifacts_id_seq",
                    privilege,
                    sequence=True,
                )

        for privilege in ("SELECT", "INSERT", "UPDATE"):
            assert _has_privilege(
                connection, "dmitri_runtime", "public.artifacts", privilege
            )
        for privilege in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            assert not _has_privilege(
                connection, "dmitri_runtime", "public.artifacts", privilege
            )
        for privilege in ("SELECT", "USAGE"):
            assert _has_privilege(
                connection,
                "dmitri_runtime",
                "public.artifacts_id_seq",
                privilege,
                sequence=True,
            )

    _migrate(engine, "head")


def test_agent_id_foreign_key_enforced_and_nullable(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as session:
        org = _seed_org(session)
        agent = _seed_agent(session, org.id)

        scan = ScanRecord(
            scan_id=uuid4(),
            agent_id=agent.id,
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="standard",
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)
        assert scan.agent_id == agent.id

    with Session(migrated_database) as session:
        session.add(
            ScanRecord(
                scan_id=uuid4(),
                agent_id=None,
                timestamp=datetime.now(timezone.utc),
                subnet="192.168.1.0/24",
                scan_mode="standard",
            )
        )
        session.commit()

    with Session(migrated_database) as session:
        session.add(
            ScanRecord(
                scan_id=uuid4(),
                agent_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
                subnet="192.168.1.0/24",
                scan_mode="standard",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
