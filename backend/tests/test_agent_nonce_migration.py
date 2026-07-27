from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
import sqlmodel
from api.models.command import Agent, AgentNonce
from api.models.identity import Org
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from test_migrations import _has_privilege

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260724_09_agent_nonces.py"
    spec = importlib.util.spec_from_file_location("task_2_agent_nonces", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260724_09"
    assert migration.down_revision == "20260724_08"


def test_migration_creates_table_and_fence(monkeypatch) -> None:
    migration = _load_migration()
    created: dict[str, sa.Table] = {}
    indexes: list[tuple[str, str, list[str], bool]] = []
    executed: list[str] = []
    metadata = sa.MetaData()

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

    assert set(created) == {"agent_nonces"}
    table = created["agent_nonces"]
    columns = {column.name for column in table.columns}
    assert columns == {"id", "agent_id", "nonce", "expires_at", "created_at"}

    assert isinstance(table.c.id.type, sa.Uuid)
    assert isinstance(table.c.agent_id.type, sa.Uuid)
    assert isinstance(table.c.nonce.type, sqlmodel.sql.sqltypes.AutoString)
    assert isinstance(table.c.expires_at.type, sa.DateTime)
    assert table.c.expires_at.type.timezone is True
    assert isinstance(table.c.created_at.type, sa.DateTime)
    assert table.c.created_at.type.timezone is True

    agent_id_fk = next(iter(created["agent_nonces"].foreign_keys))
    assert agent_id_fk.target_fullname == "agents.id"

    unique_column_sets = {
        (constraint.name, tuple(sorted(column.name for column in constraint.columns)))
        for constraint in created["agent_nonces"].constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    assert (
        "uq_agent_nonces_agent_id_nonce",
        ("agent_id", "nonce"),
    ) in unique_column_sets

    assert indexes == [
        ("ix_agent_nonces_expires_at", "agent_nonces", ["expires_at"], False)
    ]

    statements = tuple(" ".join(statement.split()) for statement in executed)
    assert statements == (
        "ALTER TABLE public.agent_nonces ENABLE ROW LEVEL SECURITY",
        (
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            "'anon') THEN REVOKE ALL PRIVILEGES ON TABLE "
            "public.agent_nonces FROM anon; END IF; END $$"
        ),
        (
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            "'authenticated') THEN REVOKE ALL PRIVILEGES ON TABLE public.agent_nonces "
            "FROM authenticated; END IF; END $$"
        ),
        "GRANT SELECT, INSERT, DELETE ON TABLE public.agent_nonces TO dmitri_runtime",
    )


def test_migration_downgrade_drops_table_and_grants(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[str] = []
    executed: list[str] = []

    monkeypatch.setattr(migration.op, "drop_table", lambda name: dropped.append(name))
    monkeypatch.setattr(migration.op, "drop_index", lambda *a, **k: None)
    monkeypatch.setattr(migration.op, "execute", lambda sql: executed.append(str(sql)))

    migration.downgrade()

    assert dropped == ["agent_nonces"]
    assert executed == [
        "REVOKE ALL PRIVILEGES ON TABLE public.agent_nonces FROM dmitri_runtime"
    ]


def test_live_migration_round_trip(postgres_engine: Engine) -> None:
    _migrate(postgres_engine, "20260724_08")
    with postgres_engine.connect() as connection:
        tables_before = set(sa.inspect(connection).get_table_names(schema="public"))
    assert "agent_nonces" not in tables_before

    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        tables_after = set(sa.inspect(connection).get_table_names(schema="public"))
    assert "agent_nonces" in tables_after

    _migrate(postgres_engine, "20260724_08")
    with postgres_engine.connect() as connection:
        tables_after_down = set(sa.inspect(connection).get_table_names(schema="public"))
    assert "agent_nonces" not in tables_after_down

    _migrate(postgres_engine, "head")


def test_live_fence_privileges(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        rls_rows = connection.execute(
            sa.text(
                "SELECT relname, relrowsecurity FROM pg_class "
                "JOIN pg_namespace ON pg_namespace.oid = relnamespace "
                "WHERE nspname = 'public' AND relname = 'agent_nonces'"
            )
        ).all()
        assert rls_rows == [("agent_nonces", True)]

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
                    connection, api_role, "public.agent_nonces", privilege
                )

        for privilege in ("SELECT", "INSERT", "DELETE"):
            assert _has_privilege(
                connection, "dmitri_runtime", "public.agent_nonces", privilege
            )
        for privilege in ("UPDATE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            assert not _has_privilege(
                connection, "dmitri_runtime", "public.agent_nonces", privilege
            )


def test_live_unique_constraint_per_agent(migrated_database: Engine) -> None:
    with Session(migrated_database) as session:
        org = Org(name="acme")
        session.add(org)
        session.commit()
        session.refresh(org)

        agent_one = Agent(
            org_id=org.id,
            display_name="agent-1",
            public_key=b"\x01" * 32,
        )
        agent_two = Agent(
            org_id=org.id,
            display_name="agent-2",
            public_key=b"\x02" * 32,
        )
        session.add(agent_one)
        session.add(agent_two)
        session.commit()
        session.refresh(agent_one)
        session.refresh(agent_two)

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        first = AgentNonce(
            agent_id=agent_one.id, nonce="shared-nonce", expires_at=expires_at
        )
        session.add(first)
        session.commit()

        duplicate = AgentNonce(
            agent_id=agent_one.id, nonce="shared-nonce", expires_at=expires_at
        )
        session.add(duplicate)
        try:
            session.commit()
        except sa.exc.IntegrityError:
            session.rollback()
        else:
            raise AssertionError("expected duplicate (agent_id, nonce) to be rejected")

        other_agent = AgentNonce(
            agent_id=agent_two.id, nonce="shared-nonce", expires_at=expires_at
        )
        session.add(other_agent)
        session.commit()

        rows = session.exec(select(AgentNonce)).all()
        assert len(rows) == 2
