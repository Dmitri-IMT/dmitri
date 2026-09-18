from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from api.models.identity import Org
from api.models.persistence import ScanHostRecord, ScanRecord
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20260912_26"
REVISION = "20260915_27"
TABLE = "exposures"
NEW_COLUMNS = {
    "scans": {"assessment_policy_version"},
    "scan_hosts": {"machine_type", "device_profile_json"},
    "hosts": {"device_profile_json", "device_profile_policy_version"},
}
INDEXES = {
    "ix_exposures_scan_id",
    "ix_exposures_scan_host_id",
    "ix_exposures_port_id",
    "ix_exposures_role",
    "ix_exposures_attention",
}
CONSTRAINTS = {
    "ck_scan_hosts_machine_type",
    "ck_exposures_role",
    "ck_exposures_attention",
    "ck_exposures_confidence",
    "uq_exposures_exposure_id",
    "uq_exposures_scan_host_port_protocol",
    "fk_exposures_scan_id_scans",
    "fk_exposures_scan_host_id_scan_hosts",
    "fk_exposures_port_id_ports",
}
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
    path = ROOT / "alembic/versions/20260915_27_attack_surface_profiles.py"
    spec = importlib.util.spec_from_file_location("attack_surface_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _names(connection: sa.Connection, query: str) -> set[str]:
    return set(connection.execute(sa.text(query)).scalars().all())


def _schema_state(connection: sa.Connection) -> tuple[set[str], ...]:
    columns = set()
    for table, expected in NEW_COLUMNS.items():
        rows = connection.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": table},
        ).scalars()
        columns.update(f"{table}.{name}" for name in set(rows).intersection(expected))
    return (
        _names(
            connection,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'exposures'",
        ),
        columns,
        _names(
            connection,
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND tablename = 'exposures'",
        ).intersection(INDEXES),
        _names(
            connection,
            "SELECT conname FROM pg_constraint WHERE conname LIKE '%exposures%' "
            "OR conname = 'ck_scan_hosts_machine_type'",
        ).intersection(CONSTRAINTS),
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


def test_revision_chain() -> None:
    migration = _load_migration()

    assert migration.revision == REVISION
    assert migration.down_revision == PREVIOUS_REVISION


def test_round_trip_adds_and_removes_all_schema_objects(
    migrated_database: Engine,
) -> None:
    with migrated_database.connect() as connection:
        at_head = _schema_state(connection)
    expected_columns = {
        f"{table}.{column}"
        for table, columns in NEW_COLUMNS.items()
        for column in columns
    }
    assert at_head == ({TABLE}, expected_columns, INDEXES, CONSTRAINTS)

    _migrate(migrated_database, PREVIOUS_REVISION)
    try:
        with migrated_database.connect() as connection:
            assert _schema_state(connection) == (set(), set(), set(), set())
    finally:
        _migrate(migrated_database, "head")

    with migrated_database.connect() as connection:
        assert _schema_state(connection) == at_head


def test_new_columns_are_nullable_for_legacy_rows(
    administrative_session: Session, seeded_org: Org
) -> None:
    inspector = sa.inspect(administrative_session.connection())
    for table, expected_columns in NEW_COLUMNS.items():
        columns = {
            column["name"]: column
            for column in inspector.get_columns(table)
            if column["name"] in expected_columns
        }
        assert set(columns) == expected_columns
        assert all(column["nullable"] for column in columns.values())

    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded_org.id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="standard",
    )
    administrative_session.add(scan)
    administrative_session.flush()
    snapshot = ScanHostRecord(
        scan_id=scan.scan_id,
        ip="192.168.1.10",
        mac=None,
        hostname="legacy",
        vendor="unknown",
    )
    administrative_session.add(snapshot)
    administrative_session.commit()

    assert scan.assessment_policy_version is None
    assert snapshot.machine_type is None
    assert snapshot.device_profile_json is None


def test_exposure_security_fence_and_runtime_grants(
    migrated_database: Engine,
) -> None:
    qualified = "public.exposures"
    sequence = "public.exposures_id_seq"
    with migrated_database.connect() as connection:
        assert connection.execute(
            sa.text(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE relname = 'exposures' "
                "AND relnamespace = 'public'::regnamespace"
            )
        ).scalar_one()
        assert connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = 'exposures'"
            )
        ).scalar_one() == 0

        for role in ("anon", "authenticated"):
            for privilege in TABLE_PRIVILEGES:
                assert not _has_privilege(connection, role, qualified, privilege)
            for privilege in ("USAGE", "SELECT", "UPDATE"):
                assert not _has_privilege(
                    connection, role, sequence, privilege, sequence=True
                )

        for privilege in ("SELECT", "INSERT", "UPDATE"):
            assert _has_privilege(
                connection, "dmitri_runtime", qualified, privilege
            )
        for privilege in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            assert not _has_privilege(
                connection, "dmitri_runtime", qualified, privilege
            )
        for privilege in ("USAGE", "SELECT"):
            assert _has_privilege(
                connection,
                "dmitri_runtime",
                sequence,
                privilege,
                sequence=True,
            )
        assert not _has_privilege(
            connection,
            "dmitri_runtime",
            sequence,
            "UPDATE",
            sequence=True,
        )


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("role", "vulnerability", "ck_exposures_role"),
        ("attention", "high", "ck_exposures_attention"),
        ("confidence", "unknown", "ck_exposures_confidence"),
    ],
)
def test_exposure_enum_constraints_reject_unknown_values(
    administrative_session: Session,
    column: str,
    value: str,
    constraint: str,
) -> None:
    with pytest.raises(sa.exc.IntegrityError, match=constraint):
        administrative_session.execute(
            sa.text(
                "INSERT INTO exposures "
                "(exposure_id, scan_id, scan_host_id, port_id, ip, port, "
                "protocol, observed_service, role, attention, confidence, "
                "reason, evidence_json, created_at) VALUES "
                "(:exposure_id, :scan_id, 0, 0, '192.168.1.10', 22, 'tcp', "
                "'ssh', :role, :attention, :confidence, 'reason', '[]', NOW())"
            ),
            {
                "exposure_id": uuid4(),
                "scan_id": uuid4(),
                "role": value if column == "role" else "remote_access",
                "attention": value if column == "attention" else "review",
                "confidence": value if column == "confidence" else "high",
            },
        )
    administrative_session.rollback()
