from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261020_44"
down_revision = "20261019_43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "industrial_services",
        sa.Column("opcua_observation_json", sa.JSON(), nullable=True),
    )
    op.drop_constraint(
        "ck_industrial_services_protocol", "industrial_services", type_="check"
    )
    op.create_check_constraint(
        "ck_industrial_services_protocol",
        "industrial_services",
        "protocol IN ('modbus_tcp', 'opcua_tcp')",
    )
    op.create_check_constraint(
        "ck_industrial_services_opcua_observation_protocol",
        "industrial_services",
        "protocol = 'opcua_tcp' OR opcua_observation_json IS NULL",
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM industrial_services WHERE protocol = 'opcua_tcp') "
        "THEN RAISE EXCEPTION 'Cannot downgrade: OPC UA observations exist'; "
        "END IF; END $$"
    )
    op.drop_constraint(
        "ck_industrial_services_opcua_observation_protocol",
        "industrial_services",
        type_="check",
    )
    op.drop_constraint(
        "ck_industrial_services_protocol", "industrial_services", type_="check"
    )
    op.create_check_constraint(
        "ck_industrial_services_protocol",
        "industrial_services",
        "protocol IN ('modbus_tcp')",
    )
    op.drop_column("industrial_services", "opcua_observation_json")
