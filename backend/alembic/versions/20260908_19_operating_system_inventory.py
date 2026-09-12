from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260908_19"
down_revision = "20260903_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_hosts",
        sa.Column("operating_system_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "hosts",
        sa.Column("operating_system_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hosts", "operating_system_json")
    op.drop_column("scan_hosts", "operating_system_json")
