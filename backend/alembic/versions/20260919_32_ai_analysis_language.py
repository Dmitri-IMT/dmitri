from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260919_32"
down_revision = "20260919_31"
branch_labels = None
depends_on = None

TABLE = "ai_scan_analyses"
OLD_UNIQUE = "ai_scan_analyses_scan_id_key"
LANGUAGE_UNIQUE = "uq_ai_scan_analyses_scan_language"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
    )
    op.drop_constraint(OLD_UNIQUE, TABLE, type_="unique")
    op.create_unique_constraint(LANGUAGE_UNIQUE, TABLE, ["scan_id", "language"])
    op.alter_column(TABLE, "language", server_default=None)


def downgrade() -> None:
    op.drop_constraint(LANGUAGE_UNIQUE, TABLE, type_="unique")
    op.create_unique_constraint(OLD_UNIQUE, TABLE, ["scan_id"])
    op.drop_column(TABLE, "language")
