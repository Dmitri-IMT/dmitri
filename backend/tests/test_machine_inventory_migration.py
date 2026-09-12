from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from api.core.machine_type import MACHINE_TYPES
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]

PREVIOUS_REVISION = "20260905_19"
REVISION = "20260907_20"
NEW_TABLES = ("host_ports", "host_findings")
NEW_INDEXES = ("ix_hosts_org_id_last_seen_at", "ix_hosts_org_id_vulnerability_count")
NEW_COLUMNS = ("machine_type", "vulnerability_count")
CONSTRAINT = "ck_hosts_machine_type"
TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)


def _load_migration():
    path = ROOT / f"alembic/versions/{REVISION}_machine_inventory_depth.py"
    spec = importlib.util.spec_from_file_location("task_3_machine_inventory", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _insert_host(connection: sa.Connection, host_id) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO hosts (id, org_id, identity_key, ip, mac, hostname, "
            "vendor, open_ports_count, highest_severity, first_seen_at, "
            "last_seen_at, created_at, updated_at) "
            "VALUES (:id, NULL, :identity_key, '192.168.1.10', NULL, 'nas', "
            "'Synology', 2, NULL, NOW(), NOW(), NOW(), NOW())"
        ),
        {"id": host_id, "identity_key": f"key-{host_id}"},
    )


def _delete_host(connection: sa.Connection, host_id) -> None:
    connection.execute(
        sa.text("DELETE FROM hosts WHERE id = :id"), {"id": host_id}
    )


def _existing(connection: sa.Connection, query: str) -> set[str]:
    return set(connection.execute(sa.text(query)).scalars().all())


def _schema_state(connection: sa.Connection) -> tuple[set[str], ...]:
    return (
        _existing(
            connection,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND table_name IN ('host_ports', 'host_findings')",
        ),
        _existing(
            connection,
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexname IN ('ix_hosts_org_id_last_seen_at', "
            "'ix_hosts_org_id_vulnerability_count')",
        ),
        _existing(
            connection,
            "SELECT conname FROM pg_constraint "
            f"WHERE conname = '{CONSTRAINT}'",
        ),
        _existing(
            connection,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'hosts' "
            "AND column_name IN ('machine_type', 'vulnerability_count')",
        ),
    )


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
            {"role": role, "object_name": object_name, "privilege": privilege},
        ).scalar_one()
    )


def test_migration_revision_chain() -> None:
    migration = _load_migration()

    assert migration.revision == REVISION
    assert migration.down_revision == PREVIOUS_REVISION


def test_migration_allowed_set_matches_live_machine_types() -> None:
    migration = _load_migration()

    spelled = {value.strip().strip("'") for value in migration._ALLOWED.split(",")}

    assert spelled == set(MACHINE_TYPES)


def test_upgrade_stamps_nothing_retroactively(migrated_database: Engine) -> None:
    engine = migrated_database
    _migrate(engine, PREVIOUS_REVISION)
    host_id = uuid4()
    with engine.begin() as connection:
        _insert_host(connection, host_id)

    _migrate(engine, REVISION)

    try:
        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT machine_type, vulnerability_count FROM hosts "
                    "WHERE id = :id"
                ),
                {"id": host_id},
            ).one()
            assert row.machine_type is None
            assert row.vulnerability_count == 0
            for table in NEW_TABLES:
                assert (
                    connection.execute(
                        sa.text(f"SELECT count(*) FROM {table}")
                    ).scalar_one()
                    == 0
                )
    finally:
        with engine.begin() as connection:
            _delete_host(connection, host_id)
        _migrate(engine, "head")


def test_round_trip_drops_and_restores_every_object(
    migrated_database: Engine,
) -> None:
    engine = migrated_database
    with engine.connect() as connection:
        at_head = _schema_state(connection)

    assert at_head == (
        set(NEW_TABLES),
        set(NEW_INDEXES),
        {CONSTRAINT},
        set(NEW_COLUMNS),
    )

    _migrate(engine, PREVIOUS_REVISION)
    try:
        with engine.connect() as connection:
            assert _schema_state(connection) == (set(), set(), set(), set())
    finally:
        _migrate(engine, "head")

    with engine.connect() as connection:
        assert _schema_state(connection) == at_head


def test_check_constraint_admits_null_and_the_nine(
    administrative_session: Session,
) -> None:
    connection = administrative_session.connection()
    host_ids = []
    for machine_type in (None, *MACHINE_TYPES):
        host_id = uuid4()
        host_ids.append(host_id)
        _insert_host(connection, host_id)
        connection.execute(
            sa.text("UPDATE hosts SET machine_type = :value WHERE id = :id"),
            {"value": machine_type, "id": host_id},
        )

    stored = connection.execute(
        sa.text("SELECT id, machine_type FROM hosts WHERE id = ANY(:ids)"),
        {"ids": host_ids},
    ).all()

    assert {row.machine_type for row in stored} == {None, *MACHINE_TYPES}

    for host_id in host_ids:
        _delete_host(connection, host_id)
    administrative_session.commit()


def test_check_constraint_rejects_an_unknown_machine_type(
    administrative_session: Session,
) -> None:
    host_id = uuid4()
    connection = administrative_session.connection()
    _insert_host(connection, host_id)
    with pytest.raises(sa.exc.IntegrityError, match=CONSTRAINT):
        connection.execute(
            sa.text("UPDATE hosts SET machine_type = 'toaster' WHERE id = :id"),
            {"id": host_id},
        )
    administrative_session.rollback()


@pytest.mark.parametrize("table", NEW_TABLES)
def test_new_tables_carry_the_security_fence(
    migrated_database: Engine, table: str
) -> None:
    sequence = f"public.{table}_id_seq"
    qualified = f"public.{table}"
    with migrated_database.connect() as connection:
        assert connection.execute(
            sa.text(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE relname = :table "
                "AND relnamespace = 'public'::regnamespace"
            ),
            {"table": table},
        ).scalar_one()

        for role in ("anon", "authenticated"):
            for privilege in TABLE_PRIVILEGES:
                assert not _has_privilege(connection, role, qualified, privilege)
            for privilege in ("USAGE", "SELECT", "UPDATE"):
                assert not _has_privilege(
                    connection, role, sequence, privilege, sequence=True
                )

        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert _has_privilege(connection, "dmitri_runtime", qualified, privilege)
        for privilege in ("USAGE", "SELECT"):
            assert _has_privilege(
                connection, "dmitri_runtime", sequence, privilege, sequence=True
            )
