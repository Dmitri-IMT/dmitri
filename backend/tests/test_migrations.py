from __future__ import annotations

import importlib.util
import tomllib
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import context
from alembic.config import Config
from api.models import persistence
from api.models.persistence import ScanHostRecord, ScanRecord
from conftest import _assert_test_database, _migrate
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

ROOT = Path(__file__).resolve().parents[1]

# `baseline.APPLICATION_TABLES` / `APPLICATION_SEQUENCES` describe what the *baseline*
# revision created, so they are correct for the tests that exercise that revision in
# isolation but wrong for head: migration 20260722_04 renamed `devices` -> `scan_hosts`
# (identity sequence included) and later revisions added the identity, host and session
# tables. Head tables come from the model metadata, which makes the live round-trip test
# double as a model-vs-migration drift check.
HEAD_APPLICATION_TABLES = frozenset(SQLModel.metadata.tables)
SEQUENCES_RENAMED_AFTER_BASELINE = {"devices_id_seq": "scan_hosts_id_seq"}
SEQUENCES_DROPPED_AFTER_BASELINE = {"artifacts_id_seq"}

# `agent_nonces` deliberately withholds UPDATE and grants DELETE instead (nonces are
# insert-then-expire-and-delete, never mutated in place; see
# 20260724_09_agent_nonces.py). `users` adds DELETE on top of the default set for
# account removal (see 20260808_15_user_delete_cascade.py). Every other table keeps
# the default grant set.
DEFAULT_RUNTIME_GRANTS = frozenset({"SELECT", "INSERT", "UPDATE"})
RUNTIME_GRANTS_BY_TABLE = {
    "agent_nonces": frozenset({"SELECT", "INSERT", "DELETE"}),
    "users": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
}
ALL_TABLE_PRIVILEGES = frozenset(
    {"SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"}
)


def _load_alembic_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "DATABASE_URL_DIRECT", "postgresql+psycopg://user:password@host/database"
    )
    monkeypatch.setattr(context, "config", Config(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(context, "configure", lambda **kwargs: None)
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    spec = importlib.util.spec_from_file_location(
        "task_1_alembic_env", ROOT / "alembic/env.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_baseline():
    path = next((ROOT / "alembic/versions").glob("*_baseline.py"))
    spec = importlib.util.spec_from_file_location("task_2_baseline", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalise_type(compiled: str) -> str:
    """Collapse timestamp variants so baseline and model shapes stay comparable.

    Migration 20260724_08 converts every naive timestamp column to timestamptz, so
    the baseline compiles to ``TIMESTAMP WITHOUT TIME ZONE`` where the current model
    compiles to ``TIMESTAMP WITH TIME ZONE``. `_table_shape` only ever compares the
    baseline revision against current models, and the live round-trip test is what
    verifies the real column types at head, so that difference is noise here.
    """
    return "TIMESTAMP" if compiled.startswith("TIMESTAMP") else compiled


class TableShape(NamedTuple):
    columns: tuple[object, ...]
    foreign_keys: tuple[object, ...]
    unique_constraints: tuple[object, ...]
    indexes: tuple[object, ...]


def _table_shape(table: sa.Table) -> TableShape:
    dialect = postgresql.dialect()
    columns = tuple(
        (
            column.name,
            _normalise_type(column.type.compile(dialect=dialect)),
            column.nullable,
            column.primary_key,
        )
        for column in table.columns
    )
    foreign_keys = tuple(
        sorted((key.parent.name, key.target_fullname) for key in table.foreign_keys)
    )
    unique_constraints = tuple(
        sorted(
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        )
    )
    indexes = tuple(
        sorted(
            (
                index.name,
                tuple(column.name for column in index.columns),
                index.unique,
            )
            for index in table.indexes
        )
    )
    return TableShape(columns, foreign_keys, unique_constraints, indexes)


@pytest.mark.parametrize(
    "prefix",
    [
        "postgres://",
        "postgresql://",
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
    ],
)
def test_alembic_normalizes_supported_urls(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    env = _load_alembic_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL_DIRECT", f"{prefix}user:password@host/database?sslmode=require"
    )

    assert env._migration_url() == (
        "postgresql+psycopg://user:password@host/database?sslmode=require"
    )
    assert env.target_metadata is persistence.SQLModel.metadata


def test_alembic_requires_a_redacted_direct_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _load_alembic_env(monkeypatch)
    runtime_url = "postgresql+psycopg://runtime:runtime-secret@pooler.example/runtime"
    invalid_url = "sqlite://admin:direct-secret@database.example/production"
    monkeypatch.setenv("DATABASE_URL", runtime_url)
    monkeypatch.delenv("DATABASE_URL_DIRECT")

    with pytest.raises(RuntimeError) as missing:
        env._migration_url()

    assert str(missing.value) == "DATABASE_URL_DIRECT is required for migrations."
    assert runtime_url not in str(missing.value)
    assert "runtime-secret" not in str(missing.value)

    monkeypatch.setenv("DATABASE_URL_DIRECT", invalid_url)

    with pytest.raises(RuntimeError) as invalid:
        env._migration_url()

    assert str(invalid.value) == (
        "DATABASE_URL_DIRECT must be a PostgreSQL connection URL."
    )
    assert invalid_url not in str(invalid.value)
    assert "direct-secret" not in str(invalid.value)


def test_alembic_artifacts_and_backend_package_configuration() -> None:
    alembic_config = Config(ROOT / "alembic.ini")
    template = (ROOT / "alembic/script.py.mako").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert alembic_config.get_main_option("script_location") == "alembic"
    assert alembic_config.get_main_option("sqlalchemy.url") is None
    assert "import sqlmodel" in template
    assert project["project"]["version"] == "0.1.0"
    assert "alembic>=1.13" in project["project"]["dependencies"]
    assert "psycopg[binary]>=3.1.12" in project["project"]["dependencies"]
    assert not any(
        dependency.startswith("asyncpg")
        for dependency in project["project"]["dependencies"]
    )
    assert project["project"]["scripts"] == {
        "backend-worker": "api.worker_main:main",
        "backend-bootstrap-org": "api.management.bootstrap_org:main",
        "backend-provision-agent": "api.management.provision_agent:main",
    }


def test_baseline_matches_model_metadata_and_security_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _load_baseline()
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

    monkeypatch.setattr(baseline.op, "create_table", create_table)
    monkeypatch.setattr(baseline.op, "create_index", create_index)
    monkeypatch.setattr(baseline.op, "execute", lambda sql: executed.append(str(sql)))

    baseline.upgrade()

    for name, table_name, columns, unique in indexes:
        sa.Index(
            name,
            *(created[table_name].c[column] for column in columns),
            unique=unique,
        )

    assert tuple(created) == baseline.APPLICATION_TABLES
    # The baseline owns a subset of the model metadata; later migrations
    # (e.g. the identity schema) add their own tables and may extend baseline
    # tables (scans gains org_id), and the scan-host rename migration renames
    # "devices" to "scan_hosts". Assert the baseline reproduces exactly its
    # own tables' models, tolerating columns/indexes added by later
    # migrations and the later table rename.
    renamed_tables = {"devices": "scan_hosts"}
    renamed_columns = {
        ("ports", "device_id"): "scan_host_id",
        ("findings", "device_id"): "scan_host_id",
    }
    rename_affected_tables = {"devices", "ports", "findings", "scans"}
    dropped_columns = {("scans", "target_mode"), ("scans", "scan_profile")}
    dropped_tables = {"artifacts"}
    model_table_names = {
        renamed_tables.get(name, name)
        for name in created
        if name not in dropped_tables
    }
    assert model_table_names <= set(persistence.SQLModel.metadata.tables)
    for name, table in created.items():
        if name in dropped_tables:
            continue
        model_name = renamed_tables.get(name, name)
        created_shape = _table_shape(table)
        model_shape = _table_shape(persistence.SQLModel.metadata.tables[model_name])
        if name in rename_affected_tables:
            created_columns, created_fks, *_ = created_shape
            model_columns, model_fks, *_ = model_shape
            created_columns = {
                (renamed_columns.get((name, column_name), column_name), *fields)
                for column_name, *fields in created_columns
                if (name, column_name) not in dropped_columns
            }
            created_fks = {
                (
                    renamed_columns.get((name, parent), parent),
                    target.replace("devices.", "scan_hosts."),
                )
                for parent, target in created_fks
            }
            assert created_columns <= set(model_columns)
            assert created_fks <= set(model_fks)
            continue
        for created_group, model_group in zip(created_shape, model_shape):
            assert set(created_group) <= set(model_group)

    statements = tuple(" ".join(statement.split()) for statement in executed)
    tables = ", ".join(
        f"public.{table}" for table in baseline.APPLICATION_TABLES
    )
    sequences = ", ".join(
        f"public.{sequence}" for sequence in baseline.APPLICATION_SEQUENCES
    )
    expected_statements = tuple(
        f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"
        for table in baseline.APPLICATION_TABLES
    ) + tuple(
        (
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            f"'{role}') THEN REVOKE ALL PRIVILEGES ON TABLE {tables} FROM {role}; "
            f"REVOKE ALL PRIVILEGES ON SEQUENCE {sequences} FROM {role}; "
            "END IF; END $$"
        )
        for role in ("anon", "authenticated")
    ) + (
        (
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles "
        "WHERE rolname = 'dmitri_runtime') THEN "
            "CREATE ROLE dmitri_runtime WITH LOGIN PASSWORD NULL BYPASSRLS "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION; "
            "ELSE "
            "ALTER ROLE dmitri_runtime WITH LOGIN BYPASSRLS; "
            "END IF; END $$"
        ),
        (
            "DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO "
            "dmitri_runtime', current_database()); END $$"
        ),
        "GRANT USAGE ON SCHEMA public TO dmitri_runtime",
        f"GRANT SELECT, INSERT, UPDATE ON TABLE {tables} TO dmitri_runtime",
        f"GRANT USAGE, SELECT ON SEQUENCE {sequences} TO dmitri_runtime",
    )
    assert statements == expected_statements

    source = Path(baseline.__file__).read_text(encoding="utf-8").lower()
    assert "force row level security" not in source
    assert "create policy" not in source
    assert "password '" not in source
    assert "os.environ" not in source


def test_baseline_downgrade_drops_tables_and_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _load_baseline()
    dropped: list[str] = []
    executed: list[str] = []
    events: list[tuple[str, str]] = []

    def drop_table(table: str) -> None:
        dropped.append(table)
        events.append(("drop", table))

    def execute(sql: object) -> None:
        statement = " ".join(str(sql).split())
        executed.append(statement)
        events.append(("execute", statement))

    monkeypatch.setattr(baseline.op, "drop_table", drop_table)
    monkeypatch.setattr(baseline.op, "execute", execute)

    baseline.downgrade()

    assert set(dropped) == set(baseline.APPLICATION_TABLES)
    assert len(dropped) == len(baseline.APPLICATION_TABLES)
    assert executed == [
        "REVOKE USAGE ON SCHEMA public FROM dmitri_runtime",
        (
            "DO $$ BEGIN EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM "
            "dmitri_runtime', current_database()); END $$"
        ),
        (
            "DO $$ BEGIN DROP ROLE dmitri_runtime; "
            "EXCEPTION WHEN dependent_objects_still_exist THEN NULL; END $$"
        ),
    ]
    assert [kind for kind, _ in events] == ["drop"] * len(dropped) + ["execute"] * 3


class _DatabaseResult:
    def __init__(self, database: str) -> None:
        self.database = database

    def scalar_one(self) -> str:
        return self.database


class _DatabaseConnection:
    def __init__(self, database: str) -> None:
        self.database = database
        self.calls = 0

    def execute(self, statement: object) -> _DatabaseResult:
        del statement
        self.calls += 1
        return _DatabaseResult(self.database)


def test_destructive_database_guard_requires_url_and_server_match() -> None:
    wrong_url_connection = _DatabaseConnection("dmitri_test")

    with pytest.raises(RuntimeError, match="DATABASE_URL_TEST must target"):
        _assert_test_database(
            "postgresql+psycopg://u:p@localhost/postgres", wrong_url_connection
        )

    assert wrong_url_connection.calls == 0

    wrong_server_connection = _DatabaseConnection("postgres")

    with pytest.raises(RuntimeError, match="Connected database must be dmitri_test"):
        _assert_test_database(
            "postgresql+psycopg://u:p@localhost/dmitri_test",
            wrong_server_connection,
        )

    assert wrong_server_connection.calls == 1


def _has_privilege(
    connection: sa.Connection,
    role: str,
    object_name: str,
    privilege: str,
    *,
    sequence: bool = False,
) -> bool:
    function = "has_sequence_privilege" if sequence else "has_table_privilege"
    return bool(
        connection.execute(
            sa.text(f"SELECT {function}(:role, :object_name, :privilege)"),
            {
                "role": role,
                "object_name": object_name,
                "privilege": privilege,
            },
        ).scalar_one()
    )


def test_live_migration_round_trip_and_security(postgres_engine: Engine) -> None:
    baseline = _load_baseline()
    head_sequences = tuple(
        SEQUENCES_RENAMED_AFTER_BASELINE.get(sequence, sequence)
        for sequence in baseline.APPLICATION_SEQUENCES
        if sequence not in SEQUENCES_DROPPED_AFTER_BASELINE
    )

    _migrate(postgres_engine, "base")
    with postgres_engine.connect() as connection:
        tables_after_down = set(sa.inspect(connection).get_table_names(schema="public"))
    assert set(HEAD_APPLICATION_TABLES).isdisjoint(tables_after_down)

    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        tables_after_up = set(sa.inspect(connection).get_table_names(schema="public"))
        rls_rows = connection.execute(
            sa.text(
                "SELECT relname, relrowsecurity, relforcerowsecurity "
                "FROM pg_class JOIN pg_namespace ON pg_namespace.oid = relnamespace "
                "WHERE nspname = 'public' AND relname = ANY(:tables)"
            ),
            {"tables": sorted(HEAD_APPLICATION_TABLES)},
        ).all()
        policies = connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = ANY(:tables)"
            ),
            {"tables": sorted(HEAD_APPLICATION_TABLES)},
        ).scalar_one()
        role = connection.execute(
            sa.text(
                "SELECT rolcanlogin, rolbypassrls, rolsuper, rolcreatedb, "
                "rolcreaterole, rolreplication FROM pg_roles "
                "WHERE rolname = 'dmitri_runtime'"
            )
        ).one()
        role_oid = connection.execute(
            sa.text("SELECT oid FROM pg_roles WHERE rolname = 'dmitri_runtime'")
        ).scalar_one()
        owned_objects = connection.execute(
            sa.text("SELECT count(*) FROM pg_class WHERE relowner = :role_oid"),
            {"role_oid": role_oid},
        ).scalar_one()
        owned_schemas = connection.execute(
            sa.text("SELECT count(*) FROM pg_namespace WHERE nspowner = :role_oid"),
            {"role_oid": role_oid},
        ).scalar_one()
        role_memberships = connection.execute(
            sa.text("SELECT count(*) FROM pg_auth_members WHERE member = :role_oid"),
            {"role_oid": role_oid},
        ).scalar_one()
        api_role_memberships = connection.execute(
            sa.text(
                "SELECT pg_has_role('dmitri_runtime', 'anon', 'MEMBER'), "
                "pg_has_role('dmitri_runtime', 'authenticated', 'MEMBER')"
            )
        ).one()

        assert set(HEAD_APPLICATION_TABLES) <= tables_after_up
        assert {row[0] for row in rls_rows} == set(HEAD_APPLICATION_TABLES)
        assert all(row[1] is True and row[2] is False for row in rls_rows)
        assert policies == 0
        assert tuple(role) == (True, True, False, False, False, False)
        assert owned_objects == 0
        assert owned_schemas == 0
        assert role_memberships == 0
        assert tuple(api_role_memberships) == (False, False)

        for api_role in ("anon", "authenticated"):
            for table in HEAD_APPLICATION_TABLES:
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
            for sequence in head_sequences:
                for privilege in ("SELECT", "UPDATE", "USAGE"):
                    assert not _has_privilege(
                        connection,
                        api_role,
                        f"public.{sequence}",
                        privilege,
                        sequence=True,
                    )

        for table in HEAD_APPLICATION_TABLES:
            expected_grants = RUNTIME_GRANTS_BY_TABLE.get(table, DEFAULT_RUNTIME_GRANTS)
            for privilege in expected_grants:
                assert _has_privilege(
                    connection, "dmitri_runtime", f"public.{table}", privilege
                )
            for privilege in ALL_TABLE_PRIVILEGES - expected_grants:
                assert not _has_privilege(
                    connection, "dmitri_runtime", f"public.{table}", privilege
                )

        # `_table_shape` normalises timestamp variants away, so nothing else
        # catches a model that declares a timestamp column naive while its
        # migration creates it timestamptz (or the reverse). That divergence is
        # invisible until `alembic revision --autogenerate` "corrects" the column
        # back to the model and utc_now() comparisons start raising
        # "can't compare offset-naive and offset-aware datetimes" — the bug
        # 20260724_08 exists to eliminate.
        timestamp_types = {
            (row.table_name, row.column_name): row.data_type
            for row in connection.execute(
                sa.text(
                    "SELECT table_name, column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND data_type LIKE 'timestamp%'"
                )
            )
        }
        for table_name in HEAD_APPLICATION_TABLES:
            for column in SQLModel.metadata.tables[table_name].columns:
                if not isinstance(column.type, sa.DateTime):
                    continue
                data_type = timestamp_types.get((table_name, column.name))
                assert data_type is not None, f"{table_name}.{column.name} missing"
                assert column.type.timezone == (
                    data_type == "timestamp with time zone"
                ), f"{table_name}.{column.name} model/database timezone mismatch"
        for sequence in head_sequences:
            for privilege in ("SELECT", "USAGE"):
                assert _has_privilege(
                    connection,
                    "dmitri_runtime",
                    f"public.{sequence}",
                    privilege,
                    sequence=True,
                )
            assert not _has_privilege(
                connection,
                "dmitri_runtime",
                f"public.{sequence}",
                "UPDATE",
                sequence=True,
            )
        assert connection.execute(
            sa.text("SELECT has_schema_privilege('dmitri_runtime', 'public', 'USAGE')")
        ).scalar_one()
        assert not connection.execute(
            sa.text("SELECT has_schema_privilege('dmitri_runtime', 'public', 'CREATE')")
        ).scalar_one()
        assert connection.execute(
            sa.text(
                "SELECT has_database_privilege("
                "'dmitri_runtime', current_database(), 'CONNECT')"
            )
        ).scalar_one()


def test_live_migration_tolerates_preexisting_runtime_role(
    postgres_engine: Engine,
) -> None:
    _migrate(postgres_engine, "base")
    with postgres_engine.begin() as connection:
        connection.execute(
            sa.text(
                "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE "
                "rolname = 'dmitri_runtime') THEN CREATE ROLE dmitri_runtime "
                "NOLOGIN; END IF; END $$"
            )
        )

    _migrate(postgres_engine, "head")

    with postgres_engine.begin() as connection:
        application_tables = set(
            sa.inspect(connection).get_table_names(schema="public")
        )
        assert connection.execute(
            sa.text(
                "SELECT has_schema_privilege('dmitri_runtime', 'public', 'USAGE')"
            )
        ).scalar_one()
        assert connection.execute(
            sa.text(
                "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'dmitri_runtime'"
            )
        ).scalar_one()

    assert set(HEAD_APPLICATION_TABLES) <= application_tables


def _assert_runtime_denied(session: Session, statement: str) -> None:
    with pytest.raises(sa.exc.DBAPIError):
        session.execute(sa.text(statement))
    session.rollback()
    assert session.execute(sa.text("SELECT current_user")).scalar_one() == (
        "dmitri_runtime"
    )


def test_runtime_role_allows_engine_work_and_rejects_privilege_expansion(
    runtime_session: Session,
) -> None:
    scan_id = uuid4()
    runtime_session.add(
        ScanRecord(
            scan_id=scan_id,
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="standard",
        )
    )
    runtime_session.commit()
    device = ScanHostRecord(
        scan_id=scan_id,
        ip="192.168.1.10",
        hostname="camera",
        vendor="vendor",
    )
    runtime_session.add(device)
    runtime_session.commit()
    runtime_session.refresh(device)

    assert device.id is not None
    assert runtime_session.exec(
        select(ScanRecord).where(ScanRecord.scan_id == scan_id)
    ).one().subnet == "192.168.1.0/24"

    runtime_session.execute(
        sa.text("UPDATE public.scans SET subnet = :subnet WHERE scan_id = :scan_id"),
        {"subnet": "192.168.2.0/24", "scan_id": scan_id},
    )
    runtime_session.commit()
    assert runtime_session.get(ScanRecord, scan_id).subnet == "192.168.2.0/24"

    for statement in (
        "CREATE SCHEMA dmitri_runtime_forbidden",
        "CREATE TABLE public.dmitri_runtime_forbidden (id integer)",
        "ALTER TABLE public.scans ADD COLUMN forbidden integer",
        f"DELETE FROM public.scans WHERE scan_id = '{scan_id}'",
        "TRUNCATE TABLE public.scans CASCADE",
    ):
        _assert_runtime_denied(runtime_session, statement)
