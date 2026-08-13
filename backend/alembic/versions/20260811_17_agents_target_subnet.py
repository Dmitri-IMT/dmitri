from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260811_17"
down_revision = "20260810_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("target_subnet", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "target_subnet")
