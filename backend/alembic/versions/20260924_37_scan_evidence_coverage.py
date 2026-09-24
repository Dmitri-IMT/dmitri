from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_37"
down_revision = "20260924_36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("coverage_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.execute(
        "UPDATE findings SET confidence = 'probable' "
        "WHERE cve_id IS NOT NULL AND source IN ('nmap_vulners', 'nvd') "
        "AND confidence = 'confirmed'"
    )
    op.execute(
        "UPDATE findings SET evidence = replace(evidence, "
        "'NVD validated this CVE.', "
        "'NVD lists this CVE; target applicability is unverified.') "
        "WHERE cve_id IS NOT NULL AND source IN ('nmap_vulners', 'nvd') "
        "AND evidence LIKE '%NVD validated this CVE.%'"
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
          AND finding.source IN ('nmap_vulners', 'nvd')
          AND risk.confidence = 'confirmed'
        """
    )


def downgrade() -> None:
    op.drop_column("scans", "coverage_json")
