from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260722_06"
down_revision = "20260722_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("finding_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE findings SET finding_id = gen_random_uuid() WHERE finding_id IS NULL"
    )
    op.alter_column("findings", "finding_id", nullable=False)
    op.create_index(
        "uq_findings_finding_id", "findings", ["finding_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_findings_finding_id", table_name="findings")
    op.drop_column("findings", "finding_id")
