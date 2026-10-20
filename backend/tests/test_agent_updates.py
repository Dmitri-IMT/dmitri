from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from threading import get_ident
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.agent_update import (
    AgentRelease,
    AgentReleaseCatalogState,
    AgentUpdate,
    AgentUpdateEvent,
)
from api.models.command import Agent, Command
from api.models.identity import Org, User
from api.schemas.agent_updates import (
    AgentUpdateClaimRequest,
    AgentUpdateEventRequest,
    AgentUpdateEvidence,
    ReleaseSummary,
    UpdateOperationView,
)
from api.services import agent_connections, device_sig
from api.services.agent_updates import (
    UpdateProtocolError,
    claim_update,
    reconcile_update_hello,
    record_update_event,
)
from api.services.agent_updates_http import UpdateAdmissionError, _reserve
from api.services.agents import revoke_agent
from api.services.release_catalog import project_availability
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import Session, select


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _fixture_rows(session: Session, *, required_protocol_version: int = 1):
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
        required_protocol_version=required_protocol_version,
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


def _signed_headers(
    *, private_key: bytes, agent_id, path: str, body: bytes, nonce: str
):
    timestamp = datetime.now(timezone.utc).isoformat()
    body_hash = device_sig.body_sha256(body)
    canonical = device_sig.canonical_string(
        "POST", path, str(agent_id), timestamp, nonce, body_hash
    )
    return {
        "Content-Type": "application/json",
        "X-Device-Id": str(agent_id),
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Body-SHA256": body_hash,
        "X-Signature": device_sig.sign(private_key, canonical),
    }


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


def test_claim_receipt_is_idempotent_and_deadline_does_not_extend(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.claim_deadline = now.replace(microsecond=0) + timedelta(seconds=30)
    agent.version_observed_session_id = session_id
    administrative_session.add_all([operation, agent])
    administrative_session.commit()
    body = AgentUpdateClaimRequest(
        session_id=session_id,
        release_id=release.id,
        target_package_version=release.package_version,
        sha256=release.sha256,
    )

    receipt = claim_update(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=body,
        current_session_id=session_id,
        now=now,
    )
    repeated = claim_update(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=body,
        current_session_id=uuid4(),
        now=now + timedelta(minutes=5),
    )
    assert receipt == repeated
    assert receipt.required_updater_version == release.required_updater_version
    administrative_session.refresh(operation)
    assert operation.phase == "preparing"
    assert operation.authorization_deadline == receipt.authorization_deadline


def test_expired_claim_is_persisted_and_cannot_be_reclaimed(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.claim_deadline = now
    administrative_session.add(operation)
    administrative_session.commit()
    body = AgentUpdateClaimRequest(
        session_id=session_id,
        release_id=release.id,
        target_package_version=release.package_version,
        sha256=release.sha256,
    )
    with pytest.raises(UpdateProtocolError, match="request_expired"):
        claim_update(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=body,
            current_session_id=session_id,
            now=now + timedelta(seconds=1),
        )
    administrative_session.refresh(operation)
    assert operation.phase == "expired"


def test_signed_claim_endpoint_binds_current_session_and_rejects_nonce_replay(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
) -> None:
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    provisioned_agent.version_observed_session_id = session_id
    user = User(
        org_id=seeded_org.id,
        email=f"claim-{uuid4()}@example.test",
        password_hash="hash",
        role="admin",
    )
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
        published_at=now,
    )
    administrative_session.add_all([user, release, provisioned_agent])
    administrative_session.flush()
    operation = _operation(seeded_org, user, provisioned_agent, release)
    operation.session_id = session_id
    operation.claim_deadline = now + timedelta(seconds=30)
    administrative_session.add(operation)
    administrative_session.commit()
    websocket = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, websocket, now=now))
    connection = agent_connections.get_connection(provisioned_agent.id)
    assert connection is not None
    connection.session_id = session_id
    connection.capabilities = frozenset({"agent_update_v1"})
    body = {
        "session_id": str(session_id),
        "release_id": str(release.id),
        "target_package_version": release.package_version,
        "sha256": release.sha256,
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    path = f"/api/v1/agent-updates/{operation.id}/claim"
    private_key, _ = agent_keypair
    headers = _signed_headers(
        private_key=private_key,
        agent_id=provisioned_agent.id,
        path=path,
        body=raw,
        nonce=uuid4().hex,
    )

    first = client.post(path, content=raw, headers=headers)
    replay = client.post(path, content=raw, headers=headers)
    assert first.status_code == 200
    assert first.json()["session_id"] == str(session_id)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "unauthorized"
    administrative_session.refresh(operation)
    assert operation.phase == "preparing"


def test_revocation_blocks_event_reporting_without_fabricating_local_failure(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    operation = _operation(org, user, agent, release)
    operation.session_id = uuid4()
    operation.phase = "needs_intervention"
    operation.local_outcome = "needs_intervention"
    agent.revoked_at = now
    administrative_session.add_all([operation, agent])
    administrative_session.commit()
    body = AgentUpdateEventRequest(
        sequence=1,
        phase="recovering",
        local_outcome="needs_intervention",
        session_id=operation.session_id,
        occurred_at=now,
    )
    with pytest.raises(UpdateProtocolError, match="device_revoked"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=body,
            now=now,
            current_session_id=None,
        )
    administrative_session.refresh(operation)
    assert operation.phase == "needs_intervention"
    assert operation.local_outcome == "needs_intervention"


def test_event_sequence_conflicts_and_hello_event_reconcile_both_orders(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    invocation_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.claim_deadline = now + timedelta(seconds=30)
    agent.version_observed_session_id = session_id
    agent.observed_version = operation.target_version
    agent.observed_package_version = operation.target_package_version
    administrative_session.add_all([operation, agent])
    administrative_session.commit()
    claim = AgentUpdateClaimRequest(
        session_id=session_id,
        release_id=release.id,
        target_package_version=release.package_version,
        sha256=release.sha256,
    )
    claim_update(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=claim,
        current_session_id=session_id,
        now=now,
    )

    def report(sequence: int, phase: str, **kwargs) -> AgentUpdateEventRequest:
        body = AgentUpdateEventRequest(
            sequence=sequence,
            phase=phase,
            session_id=session_id,
            occurred_at=now,
            **kwargs,
        )
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=body,
            now=now,
            current_session_id=session_id,
        )
        return body

    with pytest.raises(UpdateProtocolError, match="sequence_out_of_order"):
        report(2, "installing")
    first = report(1, "installing")
    assert (
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=first,
            now=now,
            current_session_id=session_id,
        )
        == 1
    )
    with pytest.raises(UpdateProtocolError, match="sequence_conflict"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=first.model_copy(update={"phase": "verifying"}),
            now=now,
            current_session_id=session_id,
        )
    report(2, "verifying")
    health = AgentUpdateEvidence(
        package_status="configured", service_active=True, health_check="passed"
    )
    report(
        3,
        "awaiting_confirmation",
        local_outcome="succeeded",
        observed_version=operation.target_version,
        package_version=operation.target_package_version,
        invocation_id=invocation_id,
        evidence=health,
    )
    administrative_session.refresh(operation)
    assert operation.phase == "awaiting_confirmation"
    assert operation.local_outcome == "succeeded"
    assert operation.confirmed_at is None

    agent_row = administrative_session.get(Agent, agent.id)
    assert agent_row is not None
    reconcile_update_hello(
        administrative_session,
        agent=agent_row,
        session_id=session_id,
        update_id=operation.id,
        invocation_id=invocation_id,
        agent_version=operation.target_version,
        package_version=operation.target_package_version,
        now=now,
    )
    administrative_session.commit()
    administrative_session.refresh(operation)
    assert operation.phase == "succeeded"
    assert operation.confirmed_at == now


def test_hello_before_local_event_and_hello_alone_cannot_confirm(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    invocation_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.claim_deadline = now + timedelta(seconds=30)
    agent.version_observed_session_id = session_id
    agent.observed_version = operation.target_version
    agent.observed_package_version = operation.target_package_version
    administrative_session.add_all([operation, agent])
    administrative_session.commit()
    claim_update(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=AgentUpdateClaimRequest(
            session_id=session_id,
            release_id=release.id,
            target_package_version=release.package_version,
            sha256=release.sha256,
        ),
        current_session_id=session_id,
        now=now,
    )
    # A matching hello without durable local health evidence cannot confirm.
    agent_row = administrative_session.get(Agent, agent.id)
    assert agent_row is not None
    reconcile_update_hello(
        administrative_session,
        agent=agent_row,
        session_id=session_id,
        update_id=operation.id,
        invocation_id=invocation_id,
        agent_version=operation.target_version,
        package_version=operation.target_package_version,
        now=now,
    )
    administrative_session.commit()
    administrative_session.refresh(operation)
    assert operation.phase == "preparing"

    def report(sequence: int, phase: str, **kwargs) -> None:
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=AgentUpdateEventRequest(
                sequence=sequence,
                phase=phase,
                session_id=session_id,
                occurred_at=now,
                **kwargs,
            ),
            now=now,
            current_session_id=session_id,
            hello_context=(operation.id, invocation_id),
            hello_agent_version=operation.target_version,
            hello_package_version=operation.target_package_version,
        )

    report(1, "installing")
    report(2, "verifying")
    report(
        3,
        "awaiting_confirmation",
        local_outcome="succeeded",
        observed_version=operation.target_version,
        package_version=operation.target_package_version,
        invocation_id=invocation_id,
        evidence=AgentUpdateEvidence(
            package_status="configured", service_active=True, health_check="passed"
        ),
    )
    administrative_session.refresh(operation)
    assert operation.phase == "succeeded"


def test_late_installing_event_uses_claim_time_and_preserves_replay(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    claimed_at = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.claim_deadline = claimed_at + timedelta(seconds=30)
    agent.version_observed_session_id = session_id
    administrative_session.add(operation)
    administrative_session.commit()
    receipt = claim_update(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=AgentUpdateClaimRequest(
            session_id=session_id,
            release_id=release.id,
            target_package_version=release.package_version,
            sha256=release.sha256,
        ),
        current_session_id=session_id,
        now=claimed_at,
    )
    occurred_at = claimed_at + timedelta(seconds=10)
    arrived_at = receipt.authorization_deadline + timedelta(minutes=5)
    event = AgentUpdateEventRequest(
        sequence=1,
        phase="installing",
        session_id=session_id,
        occurred_at=occurred_at,
    )
    args = dict(
        agent_id=agent.id,
        update_id=operation.id,
        body=event,
        now=arrived_at,
        current_session_id=session_id,
    )
    assert record_update_event(administrative_session, **args) == 1
    assert record_update_event(administrative_session, **args) == 1
    administrative_session.refresh(operation)
    assert operation.phase == "installing"
    assert operation.mutation_started_at == occurred_at
    assert operation.authorization_deadline == receipt.authorization_deadline
    regressing = event.model_copy(
        update={"sequence": 2, "phase": "verifying", "occurred_at": claimed_at}
    )
    with pytest.raises(UpdateProtocolError, match="invalid_event_time"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=regressing,
            now=arrived_at,
            current_session_id=session_id,
        )


def test_invalid_install_time_does_not_expire_or_release_reservation(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    claimed_at = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.claim_deadline = claimed_at + timedelta(seconds=30)
    agent.version_observed_session_id = session_id
    administrative_session.add(operation)
    administrative_session.commit()
    receipt = claim_update(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=AgentUpdateClaimRequest(
            session_id=session_id,
            release_id=release.id,
            target_package_version=release.package_version,
            sha256=release.sha256,
        ),
        current_session_id=session_id,
        now=claimed_at,
    )
    event = AgentUpdateEventRequest(
        sequence=1,
        phase="installing",
        session_id=session_id,
        occurred_at=receipt.authorization_deadline + timedelta(seconds=1),
    )
    with pytest.raises(UpdateProtocolError, match="authorization_expired"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=event,
            now=receipt.authorization_deadline + timedelta(minutes=1),
            current_session_id=session_id,
        )
    administrative_session.refresh(operation)
    assert operation.phase == "preparing"
    assert operation.mutation_started_at is None


def test_event_phase_outcome_and_rollback_evidence_are_coherent(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.session_id = session_id
    operation.phase = "recovering"
    operation.claimed_at = now - timedelta(seconds=5)
    operation.authorization_deadline = now + timedelta(minutes=10)
    operation.mutation_started_at = now - timedelta(seconds=3)
    operation.previous_version = "1.0.0"
    operation.previous_package_version = "1.0.0-1"
    administrative_session.add(operation)
    administrative_session.commit()

    failed_success = AgentUpdateEventRequest(
        sequence=1,
        phase="failed",
        local_outcome="succeeded",
        error_code="install_failed",
        session_id=session_id,
        occurred_at=now,
    )
    with pytest.raises(UpdateProtocolError, match="invalid_event_combination"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=failed_success,
            now=now,
            current_session_id=session_id,
        )

    inadequate_rollback = AgentUpdateEventRequest(
        sequence=1,
        phase="rolled_back",
        local_outcome="rolled_back",
        observed_version="1.0.0",
        package_version="1.0.0-1",
        invocation_id=uuid4(),
        session_id=session_id,
        occurred_at=now,
    )
    with pytest.raises(UpdateProtocolError, match="invalid_event_combination"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=inadequate_rollback,
            now=now,
            current_session_id=session_id,
        )

    intervention = AgentUpdateEventRequest(
        sequence=1,
        phase="needs_intervention",
        local_outcome="needs_intervention",
        error_code="recovery_failed",
        session_id=session_id,
        occurred_at=now,
    )
    assert (
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=intervention,
            now=now,
            current_session_id=session_id,
        )
        == 1
    )
    administrative_session.refresh(operation)
    assert operation.phase == "needs_intervention"
    # A second active operation is rejected by the partial unique reservation.
    another = _operation(org, user, agent, release, key="blocked-by-intervention")
    administrative_session.add(another)
    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_preparing_expiry_requires_deadline_and_no_mutation(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.phase = "preparing"
    operation.session_id = session_id
    operation.claimed_at = now - timedelta(minutes=30)
    operation.authorization_deadline = now - timedelta(minutes=10)
    administrative_session.add(operation)
    administrative_session.commit()

    event = AgentUpdateEventRequest(
        sequence=1,
        phase="expired",
        local_outcome=None,
        error_code="request_expired",
        session_id=session_id,
        occurred_at=now - timedelta(minutes=10),
    )
    assert (
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=event,
            now=now,
            current_session_id=session_id,
        )
        == 1
    )
    administrative_session.refresh(operation)
    assert operation.phase == "expired"
    assert operation.local_outcome is None
    assert operation.error_code == "request_expired"

    replacement = _operation(org, user, agent, release, key="after-preparing-expiry")
    administrative_session.add(replacement)
    administrative_session.commit()
    administrative_session.delete(replacement)
    administrative_session.commit()

    blocked = _operation(org, user, agent, release, key="mutation-already-started")
    blocked.phase = "preparing"
    blocked.session_id = session_id
    blocked.claimed_at = now - timedelta(minutes=30)
    blocked.authorization_deadline = now - timedelta(minutes=10)
    blocked.mutation_started_at = now - timedelta(minutes=20)
    administrative_session.add(blocked)
    administrative_session.commit()
    with pytest.raises(UpdateProtocolError, match="illegal_transition"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=blocked.id,
            body=event,
            now=now,
            current_session_id=session_id,
        )


def test_recovery_preserves_install_cause_and_requires_rollback_health(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.phase = "installing"
    operation.session_id = session_id
    operation.claimed_at = now - timedelta(minutes=1)
    operation.mutation_started_at = now - timedelta(seconds=30)
    operation.previous_version = "1.0.0"
    operation.previous_package_version = "1.0.0-1"
    administrative_session.add(operation)
    administrative_session.commit()

    def report(sequence: int, phase: str, **kwargs) -> None:
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=AgentUpdateEventRequest(
                sequence=sequence,
                phase=phase,
                session_id=session_id,
                occurred_at=now + timedelta(seconds=sequence),
                **kwargs,
            ),
            now=now + timedelta(seconds=sequence),
            current_session_id=session_id,
        )

    report(1, "recovering", error_code="install_failed")
    report(2, "recovering", error_code="install_failed")
    administrative_session.refresh(operation)
    assert operation.error_code == "install_failed"
    report(
        3,
        "rolled_back",
        local_outcome="rolled_back",
        error_code="install_failed",
        observed_version="1.0.0",
        package_version="1.0.0-1",
        invocation_id=uuid4(),
        evidence=AgentUpdateEvidence(
            package_status="configured", service_active=True, health_check="passed"
        ),
    )
    administrative_session.refresh(operation)
    assert operation.phase == "rolled_back"
    assert operation.local_outcome == "rolled_back"
    assert operation.error_code == "install_failed"


def test_authorization_expiry_after_installing_uses_valid_recovery_outcome(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.phase = "installing"
    operation.session_id = session_id
    operation.claimed_at = now - timedelta(minutes=1)
    operation.mutation_started_at = now - timedelta(seconds=10)
    operation.previous_version = "1.0.0"
    operation.previous_package_version = "1.0.0-1"
    administrative_session.add(operation)
    administrative_session.commit()

    record_update_event(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=AgentUpdateEventRequest(
            sequence=1,
            phase="recovering",
            session_id=session_id,
            occurred_at=now,
            error_code="authorization_expired",
        ),
        now=now,
        current_session_id=session_id,
    )
    administrative_session.refresh(operation)
    assert operation.phase == "recovering"
    assert operation.error_code == "authorization_expired"

    record_update_event(
        administrative_session,
        agent_id=agent.id,
        update_id=operation.id,
        body=AgentUpdateEventRequest(
            sequence=2,
            phase="rolled_back",
            local_outcome="rolled_back",
            observed_version="1.0.0",
            package_version="1.0.0-1",
            invocation_id=uuid4(),
            session_id=session_id,
            occurred_at=now + timedelta(seconds=1),
            error_code="authorization_expired",
            evidence=AgentUpdateEvidence(
                package_status="configured", service_active=True, health_check="passed"
            ),
        ),
        now=now + timedelta(seconds=1),
        current_session_id=session_id,
    )
    administrative_session.refresh(operation)
    assert operation.phase == "rolled_back"
    assert operation.local_outcome == "rolled_back"
    assert operation.error_code == "authorization_expired"


def test_awaiting_confirmation_cannot_enter_recovery(
    administrative_session: Session,
) -> None:
    org, user, agent, release = _fixture_rows(administrative_session)
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    operation = _operation(org, user, agent, release)
    operation.phase = "awaiting_confirmation"
    operation.session_id = session_id
    operation.claimed_at = now - timedelta(minutes=1)
    operation.mutation_started_at = now - timedelta(seconds=30)
    operation.local_outcome = "succeeded"
    administrative_session.add(operation)
    administrative_session.commit()
    with pytest.raises(UpdateProtocolError, match="illegal_transition"):
        record_update_event(
            administrative_session,
            agent_id=agent.id,
            update_id=operation.id,
            body=AgentUpdateEventRequest(
                sequence=1,
                phase="recovering",
                session_id=session_id,
                occurred_at=now,
                error_code="local_health_failed",
            ),
            now=now,
            current_session_id=session_id,
        )


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


def test_update_get_routes_are_org_scoped_and_read_only(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    headers = bearer_headers(seeded_org.id, "viewer")
    before = (
        provisioned_agent.observed_version,
        provisioned_agent.observed_package_version,
        provisioned_agent.version_observed_at,
    )
    availability = client.get(
        f"/api/v1/agents/{provisioned_agent.id}/updates/availability",
        headers=headers,
    )
    history = client.get(
        f"/api/v1/agents/{provisioned_agent.id}/updates", headers=headers
    )
    operation = client.get(f"/api/v1/agent-updates/{uuid4()}", headers=headers)

    assert availability.status_code == 200
    assert availability.json()["device_readiness"] == "offline"
    assert history.status_code == 200
    assert history.json() == {"data": [], "next_cursor": None}
    assert operation.status_code == 404
    administrative_session.refresh(provisioned_agent)
    assert before == (
        provisioned_agent.observed_version,
        provisioned_agent.observed_package_version,
        provisioned_agent.version_observed_at,
    )


def test_availability_uses_update_only_negotiated_protocol(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "api.services.release_catalog.debian_version_compare",
        lambda candidate, operator, installed: False,
    )
    now = datetime.now(timezone.utc)
    provisioned_agent.observed_version = "1.0.0"
    provisioned_agent.observed_package_version = "1.0.0-1"
    provisioned_agent.version_observed_at = now
    websocket = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, websocket, now=now))
    connection = agent_connections.get_connection(provisioned_agent.id)
    assert connection is not None
    connection.capabilities = frozenset({"agent_update_v1"})
    connection.protocol_version = 1
    connection.architecture = "arm64"
    connection.os_suite = "trixie"
    connection.updater_version = "1"
    provisioned_agent.version_observed_session_id = connection.session_id
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
        published_at=now,
        approved_at=now,
    )
    administrative_session.add_all(
        [
            provisioned_agent,
            release,
            AgentReleaseCatalogState(
                singleton_id=1,
                generation=1,
                digest="c" * 64,
                validated_at=now,
                valid_until=now.replace(year=now.year + 1),
            ),
        ]
    )
    administrative_session.commit()

    response = client.get(
        f"/api/v1/agents/{provisioned_agent.id}/updates/availability",
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["availability"] == "available"
    assert response.json()["release"]["release_id"] == str(release.id)
    assert response.json()["device_readiness"] == "ready"


def test_manual_update_rejects_non_uuid_key_and_open_body(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    headers = bearer_headers(seeded_org.id, "admin")
    headers["Idempotency-Key"] = "not-a-uuid"
    response = client.post(
        f"/api/v1/agents/{provisioned_agent.id}/updates",
        headers=headers,
        json={
            "release_id": str(uuid4()),
            "expected_observed_version": "1.0.0",
            "unexpected": "rejected",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_manual_update_commits_and_delivers_once_per_idempotency_key(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    actor_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "api.services.agent_updates_http.debian_version_compare",
        lambda left, operator, right: left > right,
    )
    now = datetime.now(timezone.utc)
    provisioned_agent.observed_version = "1.0.0"
    provisioned_agent.observed_package_version = "1.0.0-1"
    provisioned_agent.version_observed_at = now
    administrative_session.add(provisioned_agent)
    websocket = AsyncMock()

    send_thread_ids: list[int] = []
    query_thread_ids: list[int] = []

    async def capture_send(_text: str) -> None:
        send_thread_ids.append(get_ident())

    def capture_query_thread(*_args) -> None:
        query_thread_ids.append(get_ident())

    websocket.send_text.side_effect = capture_send
    asyncio.run(agent_connections.register(provisioned_agent.id, websocket, now=now))
    connection = agent_connections.get_connection(provisioned_agent.id)
    assert connection is not None
    connection.capabilities = frozenset({"agent_update_v1"})
    connection.protocol_version = 1
    connection.architecture = "arm64"
    connection.os_suite = "trixie"
    connection.updater_version = "1"
    provisioned_agent.version_observed_session_id = connection.session_id
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
        published_at=now,
        approved_at=now,
    )
    administrative_session.add_all(
        [
            release,
            AgentReleaseCatalogState(
                singleton_id=1,
                generation=1,
                digest="c" * 64,
                validated_at=now,
                valid_until=now.replace(year=now.year + 1),
            ),
        ]
    )
    administrative_session.commit()

    key = str(uuid4())
    headers = actor_headers(seeded_org.id, "admin")
    headers["Idempotency-Key"] = key
    url = f"/api/v1/agents/{provisioned_agent.id}/updates"
    body = {
        "release_id": str(release.id),
        "expected_observed_version": "1.0.0",
    }

    test_engine = administrative_session.get_bind()
    event.listen(test_engine, "before_cursor_execute", capture_query_thread)
    try:
        created = client.post(url, headers=headers, json=body)
        retried = client.post(url, headers=headers, json=body)
        changed_body = client.post(
            url,
            headers=headers,
            json={**body, "expected_observed_version": "1.0.1"},
        )
    finally:
        event.remove(test_engine, "before_cursor_execute", capture_query_thread)

    assert created.status_code == 202
    assert created.headers["Location"] == (
        f"/api/v1/agent-updates/{created.json()['update_id']}"
    )
    assert retried.status_code == 200
    assert retried.json()["update_id"] == created.json()["update_id"]
    assert changed_body.status_code == 409
    assert changed_body.json()["error"]["code"] == "idempotency_conflict"
    assert websocket.send_text.await_count == 1
    assert len(send_thread_ids) == 1
    assert query_thread_ids
    assert send_thread_ids[0] not in query_thread_ids


@pytest.mark.parametrize(
    ("installed_package", "required_protocol", "comparison", "expected_error"),
    [
        ("1.2.3-1", 1, False, "release_not_allowed"),
        ("2.0.0-1", 1, False, "release_not_allowed"),
        ("1.0.0-1", 2, True, "bootstrap_required"),
    ],
    ids=["same-version", "downgrade", "protocol-not-supported"],
)
def test_manual_update_rejects_same_or_older_debian_package(
    administrative_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    installed_package: str,
    required_protocol: int,
    comparison: bool,
    expected_error: str,
) -> None:
    now = datetime.now(timezone.utc)
    org, user, agent, release = _fixture_rows(
        administrative_session, required_protocol_version=required_protocol
    )
    release.approved_at = now
    agent.observed_version = "1.2.3"
    agent.observed_package_version = installed_package
    agent.version_observed_at = now
    administrative_session.add_all(
        [
            release,
            agent,
            AgentReleaseCatalogState(
                singleton_id=1,
                generation=1,
                digest="d" * 64,
                validated_at=now,
                valid_until=now.replace(year=now.year + 1),
            ),
        ]
    )
    administrative_session.commit()
    websocket = AsyncMock()
    asyncio.run(agent_connections.register(agent.id, websocket, now=now))
    connection = agent_connections.get_connection(agent.id)
    assert connection is not None
    connection.capabilities = frozenset({"agent_update_v1"})
    connection.protocol_version = 1
    connection.architecture = "arm64"
    connection.os_suite = "trixie"
    connection.updater_version = "1"
    agent.version_observed_session_id = connection.session_id
    administrative_session.add(agent)
    administrative_session.commit()
    monkeypatch.setattr(
        "api.services.agent_updates_http.debian_version_compare",
        lambda candidate, operator, installed: comparison,
    )

    with pytest.raises(UpdateAdmissionError) as error:
        _reserve(
            administrative_session,
            agent_id=agent.id,
            org_id=org.id,
            actor_id=user.id,
            idempotency_key=uuid4(),
            release_id=release.id,
            expected_version="1.2.3",
            request_digest="e" * 64,
            now=now,
        )

    assert error.value.code == expected_error
    assert (
        administrative_session.exec(
            select(AgentUpdate).where(AgentUpdate.agent_id == agent.id)
        ).first()
        is None
    )


def test_availability_filters_other_release_suite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    trixie = AgentRelease(
        source_commit="a" * 40,
        upstream_version="1.3.0",
        package_version="1.3.0-1",
        architecture="arm64",
        suite="trixie",
        sha256="a" * 64,
        size_bytes=10,
        required_protocol_version=1,
        required_updater_version=1,
        published_at=now,
        approved_at=now,
    )
    bookworm = AgentRelease(
        source_commit="b" * 40,
        upstream_version="2.0.0",
        package_version="2.0.0-1",
        architecture="arm64",
        suite="bookworm",
        sha256="b" * 64,
        size_bytes=10,
        required_protocol_version=1,
        required_updater_version=1,
        published_at=now,
        approved_at=now,
    )
    monkeypatch.setattr(
        "api.services.release_catalog.debian_version_compare",
        lambda candidate, operator, current: candidate > current,
    )

    availability, release = project_availability(
        [bookworm, trixie],
        installed_version="1.0.0-1",
        architecture="arm64",
        suite="trixie",
        protocol_version=1,
        updater_version=1,
        catalog_valid_until=now.replace(year=now.year + 1),
        now=now,
    )

    assert availability == "available"
    assert release is trixie


def test_revocation_waits_for_device_admission_guard(
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
) -> None:
    async def revoke_while_guarded() -> None:
        async with agent_connections.device_guard(provisioned_agent.id):
            pending = asyncio.create_task(
                revoke_agent(
                    administrative_session,
                    agent_id=provisioned_agent.id,
                    org_id=seeded_org.id,
                    now=datetime.now(timezone.utc),
                )
            )
            await asyncio.sleep(0.02)
            assert not pending.done()
        assert await pending is not None

    asyncio.run(revoke_while_guarded())
