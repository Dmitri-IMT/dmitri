from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260912_26"
down_revision = "20260912_25"
branch_labels = None
depends_on = None

TABLE = "ai_scan_analyses"
INDEX = "ix_ai_scan_analyses_next_attempt_at"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(INDEX, TABLE, ["next_attempt_at"], unique=False)
    op.alter_column(TABLE, "last_error_code", new_column_name="last_error")


def downgrade() -> None:
    op.alter_column(TABLE, "last_error", new_column_name="last_error_code")
    op.drop_index(INDEX, table_name=TABLE)
    op.drop_column(TABLE, "next_attempt_at")
