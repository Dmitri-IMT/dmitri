from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261002_39"
down_revision = "20260928_38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("progress_json", sa.JSON(), nullable=True))
    op.add_column(
        "scans",
        sa.Column(
            "progress_seq",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "scans",
        sa.Column("progress_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scans", "progress_updated_at")
    op.drop_column("scans", "progress_seq")
    op.drop_column("scans", "progress_json")
