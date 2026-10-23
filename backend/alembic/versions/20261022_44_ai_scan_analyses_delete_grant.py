from __future__ import annotations

from alembic import op

revision = "20261022_44"
down_revision = "20261019_43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT DELETE ON TABLE public.ai_scan_analyses TO dmitri_runtime")


def downgrade() -> None:
    pass
