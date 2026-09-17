from __future__ import annotations

from alembic import op

revision = "20260917_27"
down_revision = "20260912_26"
branch_labels = None
depends_on = None

# `alembic_version` is Alembic's own bookkeeping table, so it is absent from the
# baseline's APPLICATION_TABLES grant loop and dmitri_runtime cannot read it. The
# CI schema gate needs exactly this one read to tell whether the hosted database
# has the revision a pull request expects, and read-only access to a single
# version string exposes no application data.


def upgrade() -> None:
    op.execute("GRANT SELECT ON TABLE public.alembic_version TO dmitri_runtime")


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT ON TABLE public.alembic_version FROM dmitri_runtime"
    )
