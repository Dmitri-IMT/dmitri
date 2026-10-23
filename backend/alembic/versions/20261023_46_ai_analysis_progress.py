from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

revision = "20261023_46"
down_revision = "20261023_45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_scan_analyses", sa.Column("progress_stage", AutoString(), nullable=True)
    )
    op.add_column(
        "ai_scan_analyses", sa.Column("progress_done", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_scan_analyses", sa.Column("progress_total", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ai_scan_analyses", "progress_total")
    op.drop_column("ai_scan_analyses", "progress_done")
    op.drop_column("ai_scan_analyses", "progress_stage")
