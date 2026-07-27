from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from test_migrations import _has_privilege, _table_shape

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260723_07_command_channel.py"
    spec = importlib.util.spec_from_file_location("task_4_command_channel", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_matches_model_metadata_and_security_fence(
    monkeypatch,
) -> None:
    migration = _load_migration()
    metadata = sa.MetaData()
    created: dict[str, sa.Table] = {}
    indexes: list[tuple[str, str, list[str], bool]] = []
    executed: list[str] = []

    def create_table(name: str, *elements: object) -> None:
        created[name] = sa.Table(name, metadata, *elements)

    def create_index(
        name: str, table_name: str, columns: list[str], *, unique: bool
    ) -> None:
        indexes.append((name, table_name, columns, unique))

    monkeypatch.setattr(migration.op, "create_table", create_table)
    monkeypatch.setattr(migration.op, "create_index", create_index)
    monkeypatch.setattr(migration.op, "execute", lambda sql: executed.append(str(sql)))

    migration.upgrade()

    for name, table_name, columns, unique in indexes:
        sa.Index(
            name,
            *(created[table_name].c[column] for column in columns),
            unique=unique,
        )

    assert tuple(created) == migration.COMMAND_TABLES

    from api.models import persistence  # noqa: F401 - registers metadata

    agents_columns_replaced_by_task_4 = {
        "secret_ciphertext",
        "secret_nonce",
        "secret_key_version",
    }

    for name, table in created.items():
        created_shape = _table_shape(table)
        model_shape = _table_shape(persistence.SQLModel.metadata.tables[name])
        created_columns = set(created_shape.columns)
        if name == "agents":
            created_columns = {
                column
                for column in created_columns
                if column[0] not in agents_columns_replaced_by_task_4
            }
        assert created_columns <= set(model_shape.columns)
        assert set(created_shape.foreign_keys) <= set(model_shape.foreign_keys)
        assert set(created_shape.unique_constraints) <= set(
            model_shape.unique_constraints
        )
        assert set(created_shape.indexes) <= set(model_shape.indexes)

    agents_columns = {column.name for column in created["agents"].columns}
    assert {"secret_ciphertext", "secret_nonce", "secret_key_version"} <= agents_columns
    assert "secret" not in agents_columns
    assert "secret_hash" not in agents_columns
    assert "org_id" in agents_columns

    commands_columns = created["commands"].columns
    assert "org_id" in commands_columns
    assert not commands_columns["scan_id"].nullable
    timestamps = {"created_at", "delivered_at", "started_at", "completed_at"}
    assert timestamps <= {column.name for column in commands_columns}
    assert "uploading_at" not in {column.name for column in commands_columns}

    scan_id_fk = next(
        key for key in created["commands"].foreign_keys if key.parent.name == "scan_id"
    )
    assert scan_id_fk.target_fullname == "scans.scan_id"
    agent_id_fk = next(
        key for key in created["commands"].foreign_keys if key.parent.name == "agent_id"
    )
    assert agent_id_fk.target_fullname == "agents.id"

    index_names = {(name, table_name) for name, table_name, _, _ in indexes}
    assert ("ix_agents_org_id", "agents") in index_names
    assert ("ix_commands_org_id", "commands") in index_names
    assert ("ix_commands_agent_id", "commands") in index_names
    unique_column_sets = {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in created["commands"].constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    assert ("scan_id",) in unique_column_sets

    statements = tuple(" ".join(statement.split()) for statement in executed)
    tables = ", ".join(f"public.{table}" for table in migration.COMMAND_TABLES)
    expected_statements = tuple(
        f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"
        for table in migration.COMMAND_TABLES
    ) + tuple(
        (
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            f"'{role}') THEN REVOKE ALL PRIVILEGES ON TABLE {tables} FROM {role}; "
            "END IF; END $$"
        )
        for role in ("anon", "authenticated")
    ) + (f"GRANT SELECT, INSERT, UPDATE ON TABLE {tables} TO dmitri_runtime",)
    assert statements == expected_statements


def test_migration_downgrade_drops_tables_and_grants(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[str] = []
    executed: list[str] = []

    monkeypatch.setattr(migration.op, "drop_table", lambda name: dropped.append(name))
    monkeypatch.setattr(migration.op, "drop_index", lambda *a, **k: None)
    monkeypatch.setattr(migration.op, "execute", lambda sql: executed.append(str(sql)))

    migration.downgrade()

    assert dropped == ["commands", "agents"]
    tables = ", ".join(f"public.{table}" for table in migration.COMMAND_TABLES)
    assert executed == [f"REVOKE ALL PRIVILEGES ON TABLE {tables} FROM dmitri_runtime"]


def test_live_migration_round_trip_and_kept_engine_queries(
    postgres_engine: Engine,
) -> None:
    _migrate(postgres_engine, "20260722_06")
    with postgres_engine.connect() as connection:
        tables_after_down = set(
            sa.inspect(connection).get_table_names(schema="public")
        )
    assert "agents" not in tables_after_down
    assert "commands" not in tables_after_down

    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        tables_after_up = set(sa.inspect(connection).get_table_names(schema="public"))
    assert {"agents", "commands"} <= tables_after_up

    with Session(postgres_engine) as session:
        session.exec(select(ScanRecord)).all()
        session.exec(sa.text("SELECT id FROM public.hosts")).all()


def test_live_fence_privileges(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        rls_rows = connection.execute(
            sa.text(
                "SELECT relname, relrowsecurity FROM pg_class "
                "JOIN pg_namespace ON pg_namespace.oid = relnamespace "
                "WHERE nspname = 'public' AND relname = ANY(:tables)"
            ),
            {"tables": ["agents", "commands"]},
        ).all()
        assert {row[0] for row in rls_rows} == {"agents", "commands"}
        assert all(row[1] is True for row in rls_rows)

        for table in ("agents", "commands"):
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
                        connection, api_role, f"public.{table}", privilege
                    )
            for privilege in ("SELECT", "INSERT", "UPDATE"):
                assert _has_privilege(
                    connection, "dmitri_runtime", f"public.{table}", privilege
                )
            for privilege in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                assert not _has_privilege(
                    connection, "dmitri_runtime", f"public.{table}", privilege
                )


def test_live_commands_scan_id_unique_constraint(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as session:
        org = Org(name="acme")
        session.add(org)
        session.commit()
        session.refresh(org)

        scan = ScanRecord(
            scan_id=uuid4(),
            org_id=org.id,
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="standard",
        )
        session.add(scan)
        session.commit()

        agent = Agent(
            org_id=org.id,
            display_name="agent-1",
            public_key=b"\x01" * 32,
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        first = Command(
            org_id=org.id,
            agent_id=agent.id,
            scan_id=scan.scan_id,
            scan_mode="standard",
            subnet="192.168.1.0/24",
            status="queued",
        )
        session.add(first)
        session.commit()

        second = Command(
            org_id=org.id,
            agent_id=agent.id,
            scan_id=scan.scan_id,
            scan_mode="standard",
            subnet="192.168.1.0/24",
            status="queued",
        )
        session.add(second)
        try:
            session.commit()
        except sa.exc.IntegrityError:
            session.rollback()
        else:
            raise AssertionError("expected duplicate scan_id to be rejected")
