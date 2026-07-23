from __future__ import annotations

from alembic import op

revision = "20260722_04"
down_revision = "20260722_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("devices", "scan_hosts")
    op.alter_column("ports", "device_id", new_column_name="scan_host_id")
    op.alter_column("findings", "device_id", new_column_name="scan_host_id")
    op.execute("ALTER SEQUENCE devices_id_seq RENAME TO scan_hosts_id_seq")


def downgrade() -> None:
    op.execute("ALTER SEQUENCE scan_hosts_id_seq RENAME TO devices_id_seq")
    op.alter_column("findings", "scan_host_id", new_column_name="device_id")
    op.alter_column("ports", "scan_host_id", new_column_name="device_id")
    op.rename_table("scan_hosts", "devices")
