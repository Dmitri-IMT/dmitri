from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260810_16"
down_revision = "20260808_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("GRANT DELETE ON TABLE public.invites TO dmitri_runtime")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON TABLE public.invites FROM dmitri_runtime")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "last_login_at")
