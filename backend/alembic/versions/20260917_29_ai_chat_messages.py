from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260917_29"
down_revision = "20260917_28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_messages",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("answer", sa.String(), nullable=False),
        sa.Column("uncertainties_json", sa.JSON(), nullable=False),
        sa.Column("referenced_finding_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.scan_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index("ix_ai_chat_messages_scan_id", "ai_chat_messages", ["scan_id"])
    op.create_index("ix_ai_chat_messages_user_id", "ai_chat_messages", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_chat_messages_user_id", table_name="ai_chat_messages")
    op.drop_index("ix_ai_chat_messages_scan_id", table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")
