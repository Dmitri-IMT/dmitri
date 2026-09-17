from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260917_27"
down_revision = "20260912_26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_scan_analyses",
        sa.Column(
            "writing_skill_version",
            sa.String(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column("ai_scan_analyses", "writing_skill_version", server_default=None)


def downgrade() -> None:
    op.drop_column("ai_scan_analyses", "writing_skill_version")
