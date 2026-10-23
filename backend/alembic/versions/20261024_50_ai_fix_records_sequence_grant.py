from __future__ import annotations

from alembic import op

revision = "20261024_50"
down_revision = "20261024_49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE public.ai_fix_records_id_seq "
        "TO dmitri_runtime"
    )


def downgrade() -> None:
    pass
