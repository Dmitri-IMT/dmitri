from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260918_30"
down_revision = "20260917_29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_messages",
        sa.Column("scope_type", sa.String(), nullable=False, server_default="scan"),
    )
    op.add_column("ai_chat_messages", sa.Column("scope_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE ai_chat_messages SET scope_id = scan_id WHERE scope_id IS NULL")
    op.alter_column("ai_chat_messages", "scope_id", nullable=False)
    op.alter_column("ai_chat_messages", "scope_type", server_default=None)
    op.create_index(
        "ix_ai_chat_messages_scope_type", "ai_chat_messages", ["scope_type"]
    )
    op.create_index("ix_ai_chat_messages_scope_id", "ai_chat_messages", ["scope_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_chat_messages_scope_id", table_name="ai_chat_messages")
    op.drop_index("ix_ai_chat_messages_scope_type", table_name="ai_chat_messages")
    op.drop_column("ai_chat_messages", "scope_id")
    op.drop_column("ai_chat_messages", "scope_type")
