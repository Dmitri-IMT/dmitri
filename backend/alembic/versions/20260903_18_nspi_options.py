from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260903_18"
down_revision = "20260811_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("commands", sa.Column("nspi_options", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("commands", "nspi_options")
