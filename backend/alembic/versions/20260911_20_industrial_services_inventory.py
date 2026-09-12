from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260911_20"
down_revision = ("20260905_19", "20260908_19")
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("scan_hosts", "hosts"):
        op.add_column(
            table,
            sa.Column(
                "industrial_services_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
        )
        op.alter_column(table, "industrial_services_json", server_default=None)


def downgrade() -> None:
    op.drop_column("hosts", "industrial_services_json")
    op.drop_column("scan_hosts", "industrial_services_json")
