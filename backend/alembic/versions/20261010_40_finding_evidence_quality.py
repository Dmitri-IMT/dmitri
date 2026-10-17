from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261010_40"
down_revision = "20261002_39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "findings", sa.Column("finding_evidence_policy_version", sa.String(64))
    )
    op.add_column("findings", sa.Column("evidence_observations_json", sa.JSON()))
    op.add_column("findings", sa.Column("issue_key", sa.String(256)))
    op.add_column(
        "findings",
        sa.Column(
            "issue_key_ambiguous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "findings",
        sa.Column(
            "evidence_truncated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "scans", sa.Column("finding_evidence_policy_version", sa.String(64))
    )
    op.add_column("scans", sa.Column("finding_observations_json", sa.JSON()))
    op.add_column(
        "scans",
        sa.Column(
            "finding_observations_truncated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        """
        UPDATE risk_snapshots AS risk
        SET confidence = 'probable',
            risk_score = LEAST(100, ROUND((
                CASE finding.severity
                    WHEN 'low' THEN 0.25
                    WHEN 'medium' THEN 0.5
                    WHEN 'high' THEN 0.75
                    WHEN 'critical' THEN 1.0
                    ELSE 0.5
                END * 45.0
                + risk.exploitability * 35.0
                + 0.75 * 15.0
                + CASE WHEN finding.port IS NOT NULL THEN 5.0 ELSE 0.0 END
            )::numeric, 2)),
            rationale = replace(risk.rationale, 'confidence=confirmed',
                                'confidence=probable'),
            updated_at = NOW()
        FROM findings AS finding
        WHERE risk.finding_id = finding.id
          AND finding.cve_id IS NOT NULL
          AND finding.source IN ('nmap_vulners', 'nvd', 'nvd_enrichment')
          AND finding.confidence = 'confirmed'
          AND risk.confidence = 'confirmed'
        """
    )
    op.execute(
        "UPDATE findings SET confidence = 'probable' "
        "WHERE cve_id IS NOT NULL "
        "AND source IN ('nmap_vulners', 'nvd', 'nvd_enrichment') "
        "AND confidence = 'confirmed'"
    )


def downgrade() -> None:
    op.drop_column("scans", "finding_observations_truncated")
    op.drop_column("scans", "finding_observations_json")
    op.drop_column("scans", "finding_evidence_policy_version")
    op.drop_column("findings", "evidence_truncated")
    op.drop_column("findings", "issue_key_ambiguous")
    op.drop_column("findings", "issue_key")
    op.drop_column("findings", "evidence_observations_json")
    op.drop_column("findings", "finding_evidence_policy_version")
