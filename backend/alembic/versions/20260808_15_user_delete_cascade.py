from __future__ import annotations

from alembic import op

revision = "20260808_15"
down_revision = "20260804_14"
branch_labels = None
depends_on = None

CASCADE_FOREIGN_KEYS = (
    ("refresh_tokens", "refresh_tokens_user_id_fkey"),
    ("password_reset_tokens", "password_reset_tokens_user_id_fkey"),
)


def upgrade() -> None:
    for table, constraint in CASCADE_FOREIGN_KEYS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )

    op.execute("GRANT DELETE ON TABLE public.users TO dmitri_runtime")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON TABLE public.users FROM dmitri_runtime")

    for table, constraint in CASCADE_FOREIGN_KEYS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, "users", ["user_id"], ["id"])
