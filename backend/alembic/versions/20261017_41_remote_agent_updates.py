from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261017_41"
down_revision = "20260928_38"
branch_labels = None
depends_on = None

PHASES = "'requested','preparing','installing','verifying','awaiting_confirmation','recovering','succeeded','failed','expired','rolled_back','needs_intervention'"
ERRORS = "'device_busy','session_replaced','request_expired','release_not_allowed','version_conflict','metadata_untrusted','metadata_expired','artifact_mismatch','unsupported_platform','prerequisite_missing','insufficient_resources','package_manager_busy','install_failed','local_health_failed','recovery_failed','state_corrupt'"
OUTCOMES = "'succeeded','failed','rolled_back','needs_intervention'"


def upgrade() -> None:
    op.add_column("agents", sa.Column("observed_version", sa.String(), nullable=True))
    op.add_column("agents", sa.Column("observed_package_version", sa.String(), nullable=True))
    op.add_column("agents", sa.Column("version_observed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agents", sa.Column("version_observed_session_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_table(
        "agent_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_commit", sa.String(), nullable=False),
        sa.Column("upstream_version", sa.String(), nullable=False),
        sa.Column("package", sa.String(), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("architecture", sa.String(), nullable=False),
        sa.Column("suite", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("required_protocol_version", sa.Integer(), nullable=False),
        sa.Column("required_updater_version", sa.Integer(), nullable=False),
        sa.Column("release_notes", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("package = 'hardware-agent'", name="ck_agent_releases_package"),
        sa.CheckConstraint("size_bytes > 0", name="ck_agent_releases_size_positive"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_agent_releases_sha256"),
        sa.CheckConstraint("required_protocol_version >= 1 AND required_updater_version >= 1", name="ck_agent_releases_requirements"),
        sa.UniqueConstraint("package", "package_version", "architecture", name="uq_agent_releases_package_version_arch"),
    )
    op.create_index("ix_agent_releases_approved_published", "agent_releases", ["approved_at", "published_at"])
    op.execute("""
        CREATE FUNCTION reject_agent_release_identity_change() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'agent release identity is immutable';
            END IF;
            IF (NEW.id, NEW.source_commit, NEW.upstream_version, NEW.package, NEW.package_version,
                NEW.architecture, NEW.suite, NEW.sha256, NEW.size_bytes,
                NEW.required_protocol_version, NEW.required_updater_version,
                NEW.release_notes, NEW.published_at)
               IS DISTINCT FROM
               (OLD.id, OLD.source_commit, OLD.upstream_version, OLD.package, OLD.package_version,
                OLD.architecture, OLD.suite, OLD.sha256, OLD.size_bytes,
                OLD.required_protocol_version, OLD.required_updater_version,
                OLD.release_notes, OLD.published_at) THEN
                RAISE EXCEPTION 'agent release identity is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER tr_agent_releases_immutable BEFORE UPDATE OR DELETE ON agent_releases FOR EACH ROW EXECUTE FUNCTION reject_agent_release_identity_change()")

    op.create_table(
        "agent_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_display_snapshot", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_releases.id"), nullable=False),
        sa.Column("previous_version", sa.String(), nullable=True),
        sa.Column("previous_package_version", sa.String(), nullable=True),
        sa.Column("target_version", sa.String(), nullable=False),
        sa.Column("target_package_version", sa.String(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invocation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("local_outcome", sa.String(), nullable=True),
        sa.Column("observed_version", sa.String(), nullable=True),
        sa.Column("observed_package_version", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("claim_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authorization_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mutation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("local_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"phase IN ({PHASES})", name="ck_agent_updates_phase"),
        sa.CheckConstraint(f"local_outcome IS NULL OR local_outcome IN ({OUTCOMES})", name="ck_agent_updates_local_outcome"),
        sa.CheckConstraint(f"error_code IS NULL OR error_code IN ({ERRORS})", name="ck_agent_updates_error_code"),
        sa.CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="ck_agent_updates_request_digest"),
        sa.CheckConstraint("idempotency_key <> ''", name="ck_agent_updates_idempotency_key"),
        sa.UniqueConstraint("org_id", "agent_id", "idempotency_key", name="uq_agent_updates_idempotency"),
    )
    op.create_index("ix_agent_updates_org_id", "agent_updates", ["org_id"])
    op.create_index("ix_agent_updates_agent_id", "agent_updates", ["agent_id"])
    op.create_index("ix_agent_updates_agent_created", "agent_updates", ["agent_id", "created_at"])
    op.create_index("ix_agent_updates_deadline", "agent_updates", ["phase", "claim_deadline"])
    op.create_index("uq_agent_updates_active_agent", "agent_updates", ["agent_id"], unique=True, postgresql_where=sa.text("phase IN ('requested','preparing','installing','verifying','awaiting_confirmation','recovering','needs_intervention')"))

    op.create_table(
        "agent_update_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("update_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_updates.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("body_digest", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("local_outcome", sa.String(), nullable=True),
        sa.Column("observed_version", sa.String(), nullable=True),
        sa.Column("observed_package_version", sa.String(), nullable=True),
        sa.Column("invocation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_agent_update_events_sequence_positive"),
        sa.CheckConstraint(f"phase IN ({PHASES})", name="ck_agent_update_events_phase"),
        sa.CheckConstraint(f"local_outcome IS NULL OR local_outcome IN ({OUTCOMES})", name="ck_agent_update_events_local_outcome"),
        sa.CheckConstraint(f"error_code IS NULL OR error_code IN ({ERRORS})", name="ck_agent_update_events_error_code"),
        sa.CheckConstraint("body_digest ~ '^[0-9a-f]{64}$'", name="ck_agent_update_events_body_digest"),
        sa.UniqueConstraint("update_id", "sequence", name="uq_agent_update_events_sequence"),
    )
    op.create_index("ix_agent_update_events_update_id", "agent_update_events", ["update_id"])
    op.create_index("ix_agent_update_events_created", "agent_update_events", ["created_at"])

    op.create_table(
        "agent_release_catalog_state",
        sa.Column("singleton_id", sa.Integer(), primary_key=True),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("singleton_id = 1", name="ck_agent_release_catalog_singleton"),
        sa.CheckConstraint("generation >= 0", name="ck_agent_release_catalog_generation"),
        sa.CheckConstraint("digest IS NULL OR digest ~ '^[0-9a-f]{64}$'", name="ck_agent_release_catalog_digest"),
    )

    tables = "agent_releases, agent_updates, agent_update_events, agent_release_catalog_state"
    for table in tables.split(", "):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        for role in ("anon", "authenticated"):
            op.execute(f"""
                DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                        REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM {role};
                    END IF;
                END $$
            """)
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO dmitri_runtime")


def downgrade() -> None:
    connection = op.get_bind()
    counts = connection.execute(sa.text("SELECT (SELECT count(*) FROM agent_updates) + (SELECT count(*) FROM agent_update_events)")).scalar_one()
    catalog = connection.execute(sa.text("SELECT count(*) FROM agent_release_catalog_state WHERE generation > 0 OR digest IS NOT NULL")).scalar_one()
    if counts or catalog:
        raise RuntimeError("Refusing downgrade: agent update records, reservations, or catalogue state would be lost")

    for table in ("agent_releases", "agent_updates", "agent_update_events", "agent_release_catalog_state"):
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM dmitri_runtime")

    op.execute("DROP TRIGGER tr_agent_releases_immutable ON agent_releases")
    op.execute("DROP FUNCTION reject_agent_release_identity_change()")
    op.drop_table("agent_release_catalog_state")
    op.drop_index("ix_agent_update_events_created", table_name="agent_update_events")
    op.drop_index("ix_agent_update_events_update_id", table_name="agent_update_events")
    op.drop_table("agent_update_events")
    op.drop_index("uq_agent_updates_active_agent", table_name="agent_updates")
    op.drop_index("ix_agent_updates_deadline", table_name="agent_updates")
    op.drop_index("ix_agent_updates_agent_created", table_name="agent_updates")
    op.drop_index("ix_agent_updates_agent_id", table_name="agent_updates")
    op.drop_index("ix_agent_updates_org_id", table_name="agent_updates")
    op.drop_table("agent_updates")
    op.drop_index("ix_agent_releases_approved_published", table_name="agent_releases")
    op.drop_table("agent_releases")
    op.drop_column("agents", "version_observed_session_id")
    op.drop_column("agents", "version_observed_at")
    op.drop_column("agents", "observed_package_version")
    op.drop_column("agents", "observed_version")
