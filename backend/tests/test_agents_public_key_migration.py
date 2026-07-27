from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from test_migrations import _has_privilege

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260724_11_agents_public_key.py"
    spec = importlib.util.spec_from_file_location(
        "task_4_agents_public_key", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260724_11"
    assert migration.down_revision == "20260724_10"


def test_migration_upgrade_drops_secret_columns_and_adds_public_key(
    monkeypatch,
) -> None:
    migration = _load_migration()
    dropped: list[tuple[str, str]] = []
    added: list[tuple[str, sa.Column]] = []

    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )

    migration.upgrade()

    assert dropped == [
        ("agents", "secret_ciphertext"),
        ("agents", "secret_nonce"),
        ("agents", "secret_key_version"),
    ]
    assert len(added) == 1
    table, column = added[0]
    assert table == "agents"
    assert column.name == "public_key"
    assert isinstance(column.type, sa.LargeBinary)
    assert column.nullable is False
    assert column.server_default is None


def test_migration_downgrade_restores_secret_columns_exactly(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[tuple[str, str]] = []
    added: list[tuple[str, sa.Column]] = []

    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )

    migration.downgrade()

    assert dropped == [("agents", "public_key")]
    added_by_name = {column.name: column for _, column in added}
    assert set(added_by_name) == {
        "secret_ciphertext",
        "secret_nonce",
        "secret_key_version",
    }
    assert isinstance(added_by_name["secret_ciphertext"].type, sa.LargeBinary)
    assert added_by_name["secret_ciphertext"].nullable is False
    assert isinstance(added_by_name["secret_nonce"].type, sa.LargeBinary)
    assert added_by_name["secret_nonce"].nullable is False
    assert isinstance(added_by_name["secret_key_version"].type, sa.Integer)
    assert added_by_name["secret_key_version"].nullable is False


def test_live_migration_round_trip_and_security_fence(
    migrated_database: Engine,
) -> None:
    postgres_engine = migrated_database
    with postgres_engine.connect() as connection:
        agents_columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'agents'"
                )
            )
        }
        assert "public_key" in agents_columns
        assert not {
            "secret_ciphertext",
            "secret_nonce",
            "secret_key_version",
        } & agents_columns

        public_key_row = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agents' "
                "AND column_name = 'public_key'"
            )
        ).one()
        assert public_key_row[0] == "NO"

        rls_row = connection.execute(
            sa.text(
                "SELECT relrowsecurity FROM pg_class "
                "JOIN pg_namespace ON pg_namespace.oid = relnamespace "
                "WHERE nspname = 'public' AND relname = 'agents'"
            )
        ).one()
        assert rls_row[0] is True

        for api_role in ("anon", "authenticated"):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert not _has_privilege(
                    connection, api_role, "public.agents", privilege
                )
        for privilege in ("SELECT", "INSERT", "UPDATE"):
            assert _has_privilege(
                connection, "dmitri_runtime", "public.agents", privilege
            )
        assert not _has_privilege(
            connection, "dmitri_runtime", "public.agents", "DELETE"
        )

    from conftest import _migrate

    _migrate(postgres_engine, "20260724_10")
    with postgres_engine.connect() as connection:
        agents_columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'agents'"
                )
            )
        }
        assert {
            "secret_ciphertext",
            "secret_nonce",
            "secret_key_version",
        } <= agents_columns
        assert "public_key" not in agents_columns

    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        agents_columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'agents'"
                )
            )
        }
        assert "public_key" in agents_columns
        assert not {
            "secret_ciphertext",
            "secret_nonce",
            "secret_key_version",
        } & agents_columns


def _agents_untouched_columns(connection: sa.Connection) -> dict[str, tuple[str, str]]:
    rows = connection.execute(
        sa.text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'agents' "
            "AND column_name IN "
            "('org_id', 'display_name', 'revoked_at', 'last_seen_at')"
        )
    )
    return {row[0]: (row[1], row[2]) for row in rows}


def test_live_upgrade_leaves_other_agent_columns_unchanged(
    migrated_database: Engine,
) -> None:
    postgres_engine = migrated_database
    from conftest import _migrate

    _migrate(postgres_engine, "20260724_10")
    with postgres_engine.connect() as connection:
        before = _agents_untouched_columns(connection)

    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        after = _agents_untouched_columns(connection)

    assert set(before) == {"org_id", "display_name", "revoked_at", "last_seen_at"}
    assert before == after


def test_no_backend_src_module_references_removed_secret_columns() -> None:
    src_root = ROOT / "src"
    removed = ("secret_ciphertext", "secret_nonce", "secret_key_version")
    offenders = [
        path
        for path in src_root.rglob("*.py")
        if any(name in path.read_text(encoding="utf-8") for name in removed)
    ]
    assert offenders == []
