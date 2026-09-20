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
    # A scan can have one row per language after this migration. Keep the
    # canonical English row (or the oldest row when English is unavailable)
    # before restoring the legacy one-row-per-scan constraint.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            f"""
            DELETE FROM {TABLE}
            WHERE analysis_id IN (
                SELECT analysis_id
                FROM (
                    SELECT analysis_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY scan_id
                               ORDER BY CASE WHEN language = 'en' THEN 0 ELSE 1 END,
                                        created_at,
                                        analysis_id
                           ) AS row_number
                    FROM {TABLE}
                ) ranked
                WHERE row_number > 1
            )
            """
        )
    )
    op.create_unique_constraint(OLD_UNIQUE, TABLE, ["scan_id"])
    op.drop_column(TABLE, "language")
