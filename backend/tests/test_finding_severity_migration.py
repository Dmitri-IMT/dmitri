from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from api.core.severity import SEVERITY_ORDER
from api.models.identity import Org
from api.models.persistence import FindingRecord, ScanRecord
from conftest import _alembic_config, _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260727_12_finding_severity_domain.py"
    spec = importlib.util.spec_from_file_location(
        "task_4_finding_severity_domain", path
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


def _seed_scan(session: Session, org_id) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="completed",
        metadata_json={},
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def _finding_row_snapshot(connection: sa.Connection) -> dict:
    rows = connection.execute(
        sa.text(
            "SELECT finding_id, scan_id, severity, title, description, "
            "recommendation, evidence, dedupe_key FROM findings ORDER BY dedupe_key"
        )
    ).mappings()
    return {str(row["finding_id"]): dict(row) for row in rows}


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260727_12"
    assert migration.down_revision == "20260724_11"


def test_migration_allowed_set_matches_live_severity_domain() -> None:
    """The revision spells its domain out literally so an edit to SEVERITY_ORDER
    cannot silently rewrite applied history — this catches the resulting drift."""
    migration = _load_migration()
    spelled = {value.strip().strip("'") for value in migration._ALLOWED.split(",")}
    assert spelled == set(SEVERITY_ORDER)


def test_migration_upgrade_creates_check_constraint(monkeypatch) -> None:
    migration = _load_migration()
    created: list[tuple[str, str, str]] = []

    class _Bind:
        def execute(self, _query):
            return type("Result", (), {"fetchall": lambda self: []})()

    monkeypatch.setattr(migration.op, "get_bind", lambda: _Bind())
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, check: created.append((name, table, check)),
    )

    migration.upgrade()

    assert len(created) == 1
    name, table, check = created[0]
    assert name == "ck_findings_severity"
    assert table == "findings"
    assert "severity IN ('low', 'medium', 'high', 'critical')" == check


def test_migration_downgrade_drops_check_constraint(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, type_="check": dropped.append((name, table, type_)),
    )

    migration.downgrade()

    assert dropped == [("ck_findings_severity", "findings", "check")]


def test_invalid_severity_is_rejected(administrative_session: Session) -> None:
    org = _seed_org(administrative_session)
    scan = _seed_scan(administrative_session, org.id)
    administrative_session.add(
        FindingRecord(
            finding_id=uuid4(),
            scan_id=scan.scan_id,
            severity="urgent",
            title="Bad severity",
            description="A finding with invalid severity.",
            recommendation="Fix it.",
            evidence="Some evidence.",
            dedupe_key=f"urgent-{uuid4()}",
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_valid_severities_commit(administrative_session: Session) -> None:
    org = _seed_org(administrative_session)
    scan = _seed_scan(administrative_session, org.id)
    for severity in ("low", "medium", "high", "critical"):
        administrative_session.add(
            FindingRecord(
                finding_id=uuid4(),
                scan_id=scan.scan_id,
                severity=severity,
                title=f"{severity} finding",
                description="A valid finding.",
                recommendation="None needed.",
                evidence="Evidence.",
                dedupe_key=f"{severity}-{uuid4()}",
            )
        )
    administrative_session.commit()


def test_live_upgrade_preserves_seeded_findings(migrated_database: Engine) -> None:
    engine = migrated_database
    _migrate(engine, "20260724_11")
    with Session(engine) as session:
        org = _seed_org(session)
        scan = _seed_scan(session, org.id)
        for severity in ("low", "medium", "high", "critical"):
            session.add(
                FindingRecord(
                    finding_id=uuid4(),
                    scan_id=scan.scan_id,
                    severity=severity,
                    title=f"{severity} title",
                    description="desc",
                    recommendation="rec",
                    evidence="ev",
                    dedupe_key=f"seed-{severity}",
                )
            )
        session.commit()

    with engine.connect() as connection:
        before = _finding_row_snapshot(connection)

    _migrate(engine, "20260727_12")
    with engine.connect() as connection:
        after = _finding_row_snapshot(connection)
        constraint = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = 'ck_findings_severity'"
            )
        ).fetchone()
        assert constraint is not None

    assert before == after

    _migrate(engine, "20260724_11")
    with engine.connect() as connection:
        constraint = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = 'ck_findings_severity'"
            )
        ).fetchone()
        assert constraint is None

    _migrate(engine, "head")


def test_upgrade_guard_fails_on_out_of_domain_severity(
    migrated_database: Engine,
) -> None:
    engine = migrated_database
    _migrate(engine, "20260724_11")
    org_id = uuid4()
    scan_id = uuid4()
    finding_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO orgs (id, name, created_at) "
                "VALUES (:id, :name, NOW())"
            ),
            {"id": org_id, "name": "guard-org"},
        )
        connection.execute(
            sa.text(
                "INSERT INTO scans "
                "(scan_id, org_id, timestamp, subnet, scan_mode, status, "
                "metadata_json, created_at) "
                "VALUES (:scan_id, :org_id, NOW(), '10.0.0.0/24', 'standard', "
                "'completed', '{}', NOW())"
            ),
            {"scan_id": scan_id, "org_id": org_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO findings "
                "(finding_id, scan_id, severity, confidence, title, description, "
                "recommendation, evidence, references_json, source_labels_json, "
                "dedupe_key, created_at, updated_at) "
                "VALUES (:finding_id, :scan_id, 'urgent', 'tentative', 't', 'd', "
                "'r', 'e', '[]', '[]', 'bad-dk', NOW(), NOW())"
            ),
            {"finding_id": finding_id, "scan_id": scan_id},
        )

    with pytest.raises(RuntimeError, match="'urgent'"):
        command.upgrade(_alembic_config(), "20260727_12")

    with engine.begin() as connection:
        connection.execute(
            sa.text("DELETE FROM findings WHERE finding_id = :finding_id"),
            {"finding_id": finding_id},
        )

    _migrate(engine, "head")
