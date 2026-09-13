from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260912_25"
down_revision = "20260912_24"
branch_labels = None
depends_on = None

TABLE = "enrichment_jobs"
INDEX = "ix_enrichment_jobs_next_attempt_at"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(INDEX, TABLE, ["next_attempt_at"], unique=False)


def downgrade() -> None:
    op.drop_index(INDEX, table_name=TABLE)
    op.drop_column(TABLE, "next_attempt_at")
