from __future__ import annotations

from alembic import op

revision = "20260922_34"
down_revision = "20260920_33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "GRANT SELECT, INSERT, DELETE ON TABLE public.ai_chat_messages "
        "TO dmitri_runtime"
    )
    op.execute("GRANT SELECT, INSERT ON TABLE public.ai_usage TO dmitri_runtime")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.ai_usage FROM dmitri_runtime")
    op.execute(
        "REVOKE ALL PRIVILEGES ON TABLE public.ai_chat_messages FROM dmitri_runtime"
    )
