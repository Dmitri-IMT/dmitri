from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261023_44"
down_revision = "20261019_43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_usage", sa.Column("cached_input_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ai_usage", sa.Column("reasoning_tokens", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ai_usage", "reasoning_tokens")
    op.drop_column("ai_usage", "cached_input_tokens")
