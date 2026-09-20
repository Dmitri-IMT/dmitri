from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260917_28"
down_revision = "20260917_27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("analyzed_findings", "failed_findings", "total_findings"):
        op.add_column(
            "ai_scan_analyses",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("ai_scan_analyses", name, server_default=None)


def downgrade() -> None:
    for name in ("total_findings", "failed_findings", "analyzed_findings"):
        op.drop_column("ai_scan_analyses", name)
