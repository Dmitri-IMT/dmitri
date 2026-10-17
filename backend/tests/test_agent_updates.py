from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.models.agent_update import (
    AgentRelease,
    AgentReleaseCatalogState,
    AgentUpdate,
    AgentUpdateEvent,
)
from api.models.command import Agent, Command
from api.models.identity import Org, User
from api.schemas.agent_updates import ReleaseSummary, UpdateOperationView
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import Session


def _fixture_rows(session: Session):
    org = Org(name=f"updates-{uuid4()}")
    session.add(org)
    session.flush()
    user = User(
        org_id=org.id,
        email=f"{uuid4()}@example.test",
        password_hash="test-hash",
        role="admin",
    )
    agent = Agent(org_id=org.id, display_name="test-agent", public_key=b"x" * 32)
    release = AgentRelease(
        source_commit="a" * 40,
        upstream_version="1.2.3",
        package_version="1.2.3-1",
        architecture="arm64",
        suite="trixie",
        sha256="b" * 64,
        size_bytes=123,
        required_protocol_version=1,
        required_updater_version=1,
        published_at=datetime.now(timezone.utc),
    )
    session.add_all([user, agent, release])
    session.flush()
    return org, user, agent, release


def _operation(org, user, agent, release, *, key="request-1"):
    return AgentUpdate(
        org_id=org.id,
        agent_id=agent.id,
        actor_id=user.id,
        actor_display_snapshot="admin@example.test",
        idempotency_key=key,
        request_digest="c" * 64,
        release_id=release.id,
        target_version="1.2.3",
        target_package_version="1.2.3-1",
    )


def test_agent_versions_start_null_and_are_not_derived_from_checkout(
    administrative_session: Session,
) -> None:
    org = Org(name=f"null-version-{uuid4()}")
    administrative_session.add(org)
    administrative_session.flush()
    agent = Agent(org_id=org.id, display_name="checkout", public_key=b"z" * 32)
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)

    assert agent.observed_version is None
    assert agent.observed_package_version is None
    assert agent.version_observed_at is None
    assert agent.version_observed_session_id is None


def test_update_constraints_enforce_phase_idempotency_and_single_active_reservation(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    first = _operation(org, user, agent, release)
    administrative_session.add(first)
    administrative_session.commit()

    first.phase = "made_up_phase"
    administrative_session.add(first)
    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_idempotency_is_unique_after_prior_operation_is_terminal(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    first = _operation(org, user, agent, release)
    first.phase = "succeeded"
    administrative_session.add(first)
    administrative_session.commit()

    administrative_session.add(_operation(org, user, agent, release))
    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_needs_intervention_keeps_active_agent_reservation(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    first = _operation(org, user, agent, release)
    first.phase = "needs_intervention"
    administrative_session.add(first)
    administrative_session.commit()

    administrative_session.add(_operation(org, user, agent, release, key="next"))
    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_catalog_state_is_singleton_and_domains_are_constrained(
    administrative_session: Session,
) -> None:
    administrative_session.add(AgentReleaseCatalogState(singleton_id=1))
    administrative_session.commit()
    administrative_session.add(AgentReleaseCatalogState(singleton_id=2))
    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()

    org, user, agent, release = _fixture_rows(administrative_session)
    administrative_session.commit()
    operation = _operation(org, user, agent, release)
    operation.local_outcome = "unknown"
    administrative_session.add(operation)
    with pytest.raises(IntegrityError) as error:
        administrative_session.commit()
    assert error.value.orig.diag.constraint_name == "ck_agent_updates_local_outcome"
    administrative_session.rollback()

    operation = _operation(org, user, agent, release, key="invalid-error")
    operation.error_code = "unknown"
    administrative_session.add(operation)
    with pytest.raises(IntegrityError) as error:
        administrative_session.commit()
    assert error.value.orig.diag.constraint_name == "ck_agent_updates_error_code"
    administrative_session.rollback()


def test_actor_deletion_preserves_display_snapshot(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    operation = _operation(org, user, agent, release)
    administrative_session.add(operation)
    administrative_session.commit()
    snapshot = operation.actor_display_snapshot

    administrative_session.delete(user)
    administrative_session.commit()
    administrative_session.refresh(operation)
    assert operation.actor_id is None
    assert operation.actor_display_snapshot == snapshot


def test_event_sequence_is_unique_and_release_identity_is_immutable(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    operation = _operation(org, user, agent, release)
    administrative_session.add(operation)
    administrative_session.flush()
    event = AgentUpdateEvent(
        update_id=operation.id,
        sequence=1,
        body_digest="d" * 64,
        phase="preparing",
        occurred_at=datetime.now(timezone.utc),
    )
    administrative_session.add(event)
    administrative_session.commit()

    administrative_session.add(
        AgentUpdateEvent(
            update_id=operation.id,
            sequence=1,
            body_digest="e" * 64,
            phase="installing",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()

    release.sha256 = "f" * 64
    with pytest.raises(DBAPIError):
        administrative_session.commit()
    administrative_session.rollback()

    release.approved_at = datetime.now(timezone.utc)
    release.withdrawn_at = datetime.now(timezone.utc)
    administrative_session.add(release)
    administrative_session.commit()

    release.id = uuid4()
    with pytest.raises(DBAPIError) as error:
        administrative_session.commit()
    assert "agent release identity is immutable" in str(error.value.orig)
    administrative_session.rollback()


def test_command_remains_scan_only(administrative_session: Session) -> None:
    assert "release_id" not in Command.__table__.columns
    assert "phase" not in Command.__table__.columns
    assert set(Command.__table__.columns).isdisjoint({"update_id", "idempotency_key"})


def test_update_schemas_are_closed_and_validate_domains() -> None:
    with pytest.raises(ValidationError):
        ReleaseSummary.model_validate(
            {
                "release_id": str(uuid4()),
                "package": "hardware-agent",
                "upstream_version": "1.0.0",
                "package_version": "1.0.0-1",
                "architecture": "arm64",
                "suite": "trixie",
                "sha256": "a" * 64,
                "size_bytes": 1,
                "required_protocol_version": 1,
                "required_updater_version": 1,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "release_notes": "ok",
                "download_url": "https://invalid.example/agent.deb",
            }
        )
    with pytest.raises(ValidationError):
        UpdateOperationView.model_validate(
            {
                "update_id": str(uuid4()),
                "agent_id": str(uuid4()),
                "release_id": str(uuid4()),
                "previous_version": None,
                "previous_package_version": None,
                "target_version": "1.0.0",
                "target_package_version": "1.0.0-1",
                "observed_version": None,
                "observed_package_version": None,
                "phase": "unknown",
                "local_outcome": None,
                "error_code": None,
                "actor_display_snapshot": "admin",
                "requested_at": datetime.now(timezone.utc),
                "claimed_at": None,
                "local_completed_at": None,
                "confirmed_at": None,
                "last_contact_at": None,
            }
        )
