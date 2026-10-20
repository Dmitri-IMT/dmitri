from __future__ import annotations

from alembic import op

revision = "20261019_43"
down_revision = "20261018_42"
branch_labels = None
depends_on = None

ERRORS = (
    "'device_busy','session_replaced','request_expired','release_not_allowed',"
    "'version_conflict','metadata_untrusted','metadata_expired','artifact_mismatch',"
    "'unsupported_platform','prerequisite_missing','insufficient_resources',"
    "'package_manager_busy','authorization_expired','install_failed',"
    "'local_health_failed','recovery_failed','state_corrupt'"
)
PREVIOUS_ERRORS = ERRORS.replace("'authorization_expired',", "")


def upgrade() -> None:
    op.drop_constraint("ck_agent_updates_error_code", "agent_updates", type_="check")
    op.drop_constraint(
        "ck_agent_update_events_error_code", "agent_update_events", type_="check"
    )
    op.create_check_constraint(
        "ck_agent_updates_error_code",
        "agent_updates",
        f"error_code IS NULL OR error_code IN ({ERRORS})",
    )
    op.create_check_constraint(
        "ck_agent_update_events_error_code",
        "agent_update_events",
        f"error_code IS NULL OR error_code IN ({ERRORS})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_updates_error_code", "agent_updates", type_="check")
    op.drop_constraint(
        "ck_agent_update_events_error_code", "agent_update_events", type_="check"
    )
    op.create_check_constraint(
        "ck_agent_updates_error_code",
        "agent_updates",
        f"error_code IS NULL OR error_code IN ({PREVIOUS_ERRORS})",
    )
    op.create_check_constraint(
        "ck_agent_update_events_error_code",
        "agent_update_events",
        f"error_code IS NULL OR error_code IN ({PREVIOUS_ERRORS})",
    )
