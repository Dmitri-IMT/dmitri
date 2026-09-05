from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260904_18"
down_revision = "20260811_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_scans_org_id_agent_id",
        "scans",
        ["org_id", "agent_id"],
    )
    op.execute(
        sa.text(
            """
            UPDATE scans AS s
            SET agent_id = c.agent_id
            FROM commands AS c
            WHERE s.scan_id = c.scan_id
              AND s.agent_id IS NULL
              AND c.agent_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_scans_org_id_agent_id", table_name="scans")
