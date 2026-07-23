from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260722_03"
down_revision = "20260716_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("scans", "target_mode")
    op.drop_column("scans", "scan_profile")
    op.add_column(
        "scans",
        sa.Column("scan_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    )
    op.add_column(
        "scans",
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="completed",
        ),
    )


def downgrade() -> None:
    op.drop_column("scans", "status")
    op.drop_column("scans", "scan_mode")
    op.add_column(
        "scans",
        sa.Column(
            "target_mode",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="subnet",
        ),
    )
    op.add_column(
        "scans",
        sa.Column(
            "scan_profile",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="lan",
        ),
    )
