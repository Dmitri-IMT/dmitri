from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260724_10"
down_revision = "20260724_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_users_org_email", table_name="users")
    op.create_index(
        "ix_users_email", "users", [sa.text("lower(email)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.create_index(
        "ix_users_org_email",
        "users",
        ["org_id", sa.text("lower(email)")],
        unique=True,
    )
