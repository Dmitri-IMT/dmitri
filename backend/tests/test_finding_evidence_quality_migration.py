from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from conftest import _migrate, _truncate_application_tables
from sqlalchemy.engine import Engine


def test_finding_evidence_migration_upgrades_and_downgrades_known_aliases(
    postgres_engine: Engine,
    request: pytest.FixtureRequest,
) -> None:
    request.addfinalizer(lambda: _migrate(postgres_engine, "head"))
    _migrate(postgres_engine, "20261002_39")
    scan_id = uuid4()
    created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    finding_ids: dict[str, int] = {}
    with postgres_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO scans "
                "(scan_id, timestamp, created_at, subnet, scan_mode, status, "
                "coverage_json) "
                "VALUES (:scan_id, :timestamp, :created_at, '192.0.2.0/24', "
                "'standard', 'completed', '[]')"
            ),
            {
                "scan_id": scan_id,
                "timestamp": created_at,
                "created_at": created_at,
            },
        )
        for source in ("nvd_enrichment", "nmap_vulners", "unreviewed"):
            result = connection.execute(
                sa.text(
                    "INSERT INTO findings "
                    "(finding_id, scan_id, source, cve_id, severity, confidence, "
                    "title, "
                    "description, recommendation, evidence, dedupe_key, "
                    "created_at, updated_at) "
                    "VALUES (:finding_id, :scan_id, :source, 'CVE-2025-1234', 'high', "
                    "'confirmed', 'Existing title', 'Existing description', "
                    "'Existing recommendation', 'Existing evidence', :dedupe_key, "
                    ":created_at, :created_at) RETURNING id"
                ),
                {
                    "scan_id": scan_id,
                    "finding_id": uuid4(),
                    "source": source,
                    "dedupe_key": source,
                    "created_at": created_at,
                },
            )
            finding_id = result.scalar_one()
            finding_ids[source] = finding_id
            if source != "nmap_vulners":
                connection.execute(
                    sa.text(
                        "INSERT INTO risk_snapshots "
                        "(finding_id, confidence, exploitability, risk_score, "
                        "rationale, created_at, updated_at) "
                        "VALUES (:finding_id, 'confirmed', 0.4, 88.0, "
                        "'severity=high, confidence=confirmed', :created_at, "
                        ":created_at)"
                    ),
                    {"finding_id": finding_id, "created_at": created_at},
                )

    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT finding.id, finding.source, finding.confidence, "
                "finding.evidence, finding.created_at, finding.updated_at, "
                "risk.confidence AS risk_confidence, risk.risk_score, "
                "finding.finding_evidence_policy_version, "
                "finding.evidence_observations_json, finding.evidence_truncated, "
                "finding.issue_key, finding.issue_key_ambiguous "
                "FROM findings AS finding LEFT JOIN risk_snapshots AS risk "
                "ON risk.finding_id = finding.id WHERE finding.scan_id = :scan_id"
            ),
            {"scan_id": scan_id},
        ).mappings().all()
    by_source = {row["source"]: row for row in rows}
    for source in ("nvd_enrichment", "nmap_vulners"):
        row = by_source[source]
        assert row["confidence"] == "probable"
        assert row["evidence"] == "Existing evidence"
        assert row["created_at"] == created_at
        assert row["updated_at"] == created_at
        assert row["finding_evidence_policy_version"] is None
        assert row["evidence_observations_json"] is None
        assert row["evidence_truncated"] is False
        assert row["issue_key"] is None
        assert row["issue_key_ambiguous"] is False
    assert by_source["nvd_enrichment"]["risk_confidence"] == "probable"
    assert by_source["nvd_enrichment"]["risk_score"] == 59.0
    assert by_source["nmap_vulners"]["risk_confidence"] is None
    assert by_source["unreviewed"]["confidence"] == "confirmed"
    assert by_source["unreviewed"]["risk_confidence"] == "confirmed"
    assert by_source["unreviewed"]["risk_score"] == 88.0

    _migrate(postgres_engine, "20261002_39")
    inspector = sa.inspect(postgres_engine)
    assert "finding_evidence_policy_version" not in {
        column["name"] for column in inspector.get_columns("findings")
    }
    assert "issue_key" not in {
        column["name"] for column in inspector.get_columns("findings")
    }
    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_heads() == (
            "20261019_43",
        )


@pytest.mark.parametrize(
    "starting_revision",
    ("20261010_40", "20261012_40", "20261017_41"),
)
def test_merge_revision_upgrades_from_each_parent(
    postgres_engine: Engine, starting_revision: str
) -> None:
    _truncate_application_tables(postgres_engine)
    _migrate(postgres_engine, "base")
    _migrate(postgres_engine, starting_revision)
    _migrate(postgres_engine, "head")
    with postgres_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_heads() == (
            "20261019_43",
        )
