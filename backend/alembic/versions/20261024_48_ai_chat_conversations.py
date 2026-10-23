from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024_48"
down_revision = "20261024_47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_chat_messages", sa.Column("conversation_id", sa.Uuid()))
    # Keep each existing user's contextual transcript together, without losing messages.
    op.execute("""
        UPDATE ai_chat_messages AS messages
        SET conversation_id = legacy.conversation_id
        FROM (
            SELECT message_id, first_value(message_id) OVER (
                PARTITION BY user_id, scope_type, scope_id
                ORDER BY created_at, message_id
            ) AS conversation_id
            FROM ai_chat_messages
        ) AS legacy
        WHERE messages.message_id = legacy.message_id
    """)
    op.alter_column("ai_chat_messages", "conversation_id", nullable=False)
    op.create_index(
        "ix_ai_chat_messages_conversation_id", "ai_chat_messages", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_chat_messages_conversation_id", table_name="ai_chat_messages")
    op.drop_column("ai_chat_messages", "conversation_id")
