from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from uuid import UUID

from sqlmodel import Session, select

from api.models.agent_update import AgentRelease, AgentUpdate, AgentUpdateEvent
from api.models.command import Agent
from api.schemas.agent_updates import (
    AgentUpdateClaimReceipt,
    AgentUpdateClaimRequest,
    AgentUpdateEventRequest,
)

CLAIM_AUTHORIZATION_SECONDS = 20 * 60
EVENT_CLOCK_SKEW = timedelta(minutes=2)


class UpdateProtocolError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status


def _lock_owned_operation(
    session: Session, *, agent_id: UUID, update_id: UUID
) -> tuple[Agent, AgentUpdate]:
    agent = session.exec(
        select(Agent).where(Agent.id == agent_id).with_for_update()
    ).first()
    if agent is None:
        session.rollback()
        raise UpdateProtocolError("not_found", 404)
    operation = session.exec(
        select(AgentUpdate)
        .where(AgentUpdate.id == update_id, AgentUpdate.agent_id == agent_id)
        .with_for_update()
    ).first()
    if operation is None:
        session.rollback()
        raise UpdateProtocolError("not_found", 404)
    if operation.org_id != agent.org_id:
        session.rollback()
        raise UpdateProtocolError("not_found", 404)
    if agent.revoked_at is not None:
        session.rollback()
        raise UpdateProtocolError("device_revoked", 403)
    return agent, operation


def _claim_receipt(
    operation: AgentUpdate, release: AgentRelease
) -> AgentUpdateClaimReceipt:
    if operation.session_id is None or operation.authorization_deadline is None:
        raise UpdateProtocolError("claim_state_invalid", 409)
    return AgentUpdateClaimReceipt(
        update_id=operation.id,
        session_id=operation.session_id,
        release_id=release.id,
        target_package_version=release.package_version,
        sha256=release.sha256,
        required_updater_version=release.required_updater_version,
        authorization_deadline=operation.authorization_deadline,
    )


def claim_update(
    session: Session,
    *,
    agent_id: UUID,
    update_id: UUID,
    body: AgentUpdateClaimRequest,
    current_session_id: UUID | None,
    now: datetime,
) -> AgentUpdateClaimReceipt:
    agent, operation = _lock_owned_operation(
        session, agent_id=agent_id, update_id=update_id
    )
    release = session.get(AgentRelease, operation.release_id)
    if release is None:
        session.rollback()
        raise UpdateProtocolError("release_not_allowed")
    if (
        body.release_id != release.id
        or body.target_package_version != release.package_version
        or body.sha256 != release.sha256
    ):
        session.rollback()
        raise UpdateProtocolError("artifact_mismatch")

    if operation.phase == "preparing":
        if body.session_id != operation.session_id:
            session.rollback()
            raise UpdateProtocolError("session_replaced")
        receipt = _claim_receipt(operation, release)
        session.rollback()
        return receipt

    if (
        operation.phase
        in {
            "installing",
            "verifying",
            "awaiting_confirmation",
            "recovering",
            "needs_intervention",
            "succeeded",
            "failed",
            "expired",
            "rolled_back",
        }
        and operation.claimed_at is not None
    ):
        if body.session_id != operation.session_id:
            session.rollback()
            raise UpdateProtocolError("session_replaced")
        receipt = _claim_receipt(operation, release)
        session.rollback()
        return receipt

    if operation.phase != "requested":
        session.rollback()
        raise UpdateProtocolError("illegal_transition")
    if operation.claim_deadline is None or operation.claim_deadline <= now:
        operation.phase = "expired"
        operation.error_code = "request_expired"
        operation.updated_at = now
        session.add(operation)
        session.commit()
        raise UpdateProtocolError("request_expired", 410)
    if (
        current_session_id is None
        or body.session_id != current_session_id
        or body.session_id != operation.session_id
        or agent.version_observed_session_id != current_session_id
    ):
        session.rollback()
        raise UpdateProtocolError("session_replaced")

    operation.phase = "preparing"
    operation.claimed_at = now
    operation.authorization_deadline = now + timedelta(
        seconds=CLAIM_AUTHORIZATION_SECONDS
    )
    operation.last_contact_at = now
    operation.updated_at = now
    session.add(operation)
    session.commit()
    session.refresh(operation)
    return _claim_receipt(operation, release)


_TRANSITIONS: dict[str, frozenset[str]] = {
    "requested": frozenset({"failed", "expired"}),
    "preparing": frozenset({"preparing", "installing", "failed", "expired"}),
    "installing": frozenset({"installing", "verifying", "recovering"}),
    "verifying": frozenset({"verifying", "awaiting_confirmation", "recovering"}),
    "awaiting_confirmation": frozenset({"awaiting_confirmation"}),
    "recovering": frozenset({"recovering", "rolled_back", "needs_intervention"}),
    "needs_intervention": frozenset({"recovering"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "expired": frozenset(),
    "rolled_back": frozenset(),
}


def _event_digest(body: AgentUpdateEventRequest) -> str:
    canonical = json.dumps(
        body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _validate_event_combination(
    body: AgentUpdateEventRequest, operation: AgentUpdate
) -> None:
    evidence = body.evidence
    if body.phase == "awaiting_confirmation":
        valid = (
            body.local_outcome == "succeeded"
            and body.error_code is None
            and body.invocation_id is not None
            and body.observed_version == operation.target_version
            and body.package_version == operation.target_package_version
            and evidence is not None
            and evidence.package_status == "configured"
            and evidence.service_active is True
            and evidence.health_check == "passed"
        )
    elif body.phase == "failed":
        valid = (
            body.local_outcome == "failed"
            and body.error_code is not None
            and evidence is None
        )
    elif body.phase == "rolled_back":
        valid = (
            body.local_outcome == "rolled_back"
            and body.error_code in {None, operation.error_code}
            and body.invocation_id is not None
            and operation.previous_version is not None
            and operation.previous_package_version is not None
            and body.observed_version == operation.previous_version
            and body.package_version == operation.previous_package_version
            and evidence is not None
            and evidence.package_status == "configured"
            and evidence.service_active is True
            and evidence.health_check == "passed"
        )
    elif body.phase == "needs_intervention":
        valid = body.local_outcome == "needs_intervention" and body.error_code in {
            "recovery_failed",
            "state_corrupt",
            operation.error_code,
        }
    elif body.phase == "succeeded":
        valid = body.local_outcome == "succeeded" and body.error_code is None
    elif body.phase == "expired":
        valid = (
            body.local_outcome is None
            and body.error_code == "request_expired"
            and evidence is None
        )
    elif body.phase == "recovering":
        valid = (
            body.local_outcome is None
            and body.error_code
            in {"authorization_expired", "install_failed", "local_health_failed"}
            and evidence is None
        )
    elif body.phase in {"preparing", "installing", "verifying"}:
        valid = (
            body.local_outcome is None and body.error_code is None and evidence is None
        )
    else:
        valid = False
    if not valid:
        raise UpdateProtocolError("invalid_event_combination", 422)


def _is_matching_hello(
    *,
    operation: AgentUpdate,
    agent: Agent,
    hello_session_id: UUID | None,
    hello_context: tuple[UUID, UUID] | None,
    hello_agent_version: str | None,
    hello_package_version: str | None,
) -> bool:
    return bool(
        hello_session_id
        and agent.version_observed_session_id == hello_session_id
        and hello_context == (operation.id, operation.invocation_id)
        and operation.invocation_id is not None
        and operation.local_outcome == "succeeded"
        and operation.phase == "awaiting_confirmation"
        and hello_agent_version == operation.target_version
        and hello_package_version == operation.target_package_version
    )


def _confirm_if_hello_matches(
    operation: AgentUpdate,
    agent: Agent,
    *,
    now: datetime,
    hello_session_id: UUID | None,
    hello_context: tuple[UUID, UUID] | None,
    hello_agent_version: str | None,
    hello_package_version: str | None,
) -> None:
    if _is_matching_hello(
        operation=operation,
        agent=agent,
        hello_session_id=hello_session_id,
        hello_context=hello_context,
        hello_agent_version=hello_agent_version,
        hello_package_version=hello_package_version,
    ):
        operation.phase = "succeeded"
        operation.confirmed_at = now
        operation.observed_version = hello_agent_version
        operation.observed_package_version = hello_package_version


def record_update_event(
    session: Session,
    *,
    agent_id: UUID,
    update_id: UUID,
    body: AgentUpdateEventRequest,
    now: datetime,
    current_session_id: UUID | None,
    hello_context: tuple[UUID, UUID] | None = None,
    hello_agent_version: str | None = None,
    hello_package_version: str | None = None,
) -> int:
    agent, operation = _lock_owned_operation(
        session, agent_id=agent_id, update_id=update_id
    )
    if body.session_id != operation.session_id:
        session.rollback()
        raise UpdateProtocolError("session_replaced")
    if body.occurred_at.tzinfo is None or body.occurred_at.utcoffset() is None:
        session.rollback()
        raise UpdateProtocolError("invalid_event_time", 422)

    digest = _event_digest(body)
    existing = session.exec(
        select(AgentUpdateEvent).where(
            AgentUpdateEvent.update_id == update_id,
            AgentUpdateEvent.sequence == body.sequence,
        )
    ).first()
    if existing is not None:
        if existing.body_digest != digest:
            session.rollback()
            raise UpdateProtocolError("sequence_conflict")
        session.rollback()
        return body.sequence

    latest = session.exec(
        select(AgentUpdateEvent.sequence)
        .where(AgentUpdateEvent.update_id == update_id)
        .order_by(AgentUpdateEvent.sequence.desc())
        .limit(1)
    ).first()
    expected = (latest or 0) + 1
    if body.sequence != expected:
        session.rollback()
        raise UpdateProtocolError("sequence_out_of_order")

    try:
        _validate_event_combination(body, operation)
    except UpdateProtocolError:
        session.rollback()
        raise

    occurred_at = (
        body.occurred_at.astimezone(operation.claimed_at.tzinfo)
        if operation.claimed_at
        else body.occurred_at
    )
    if operation.claimed_at is not None and occurred_at < operation.claimed_at:
        session.rollback()
        raise UpdateProtocolError("invalid_event_time", 422)
    if occurred_at > now + EVENT_CLOCK_SKEW:
        session.rollback()
        raise UpdateProtocolError("invalid_event_time", 422)
    prior_event_time = session.exec(
        select(AgentUpdateEvent.occurred_at)
        .where(AgentUpdateEvent.update_id == update_id)
        .order_by(AgentUpdateEvent.sequence.desc())
        .limit(1)
    ).first()
    if prior_event_time is not None and occurred_at < prior_event_time:
        session.rollback()
        raise UpdateProtocolError("invalid_event_time", 422)

    if operation.phase == "requested":
        allowed_preclaim_rejection = (
            body.phase == "failed"
            and body.local_outcome == "failed"
            and body.error_code is not None
            and current_session_id is not None
            and current_session_id == operation.session_id
            and body.session_id == current_session_id
            and operation.claim_deadline is not None
            and now < operation.claim_deadline
        )
        if not allowed_preclaim_rejection:
            session.rollback()
            raise UpdateProtocolError("claim_required")
    elif operation.phase not in {
        "preparing",
        "installing",
        "verifying",
        "awaiting_confirmation",
        "recovering",
        "needs_intervention",
    }:
        session.rollback()
        raise UpdateProtocolError("illegal_transition")

    if body.phase not in _TRANSITIONS.get(operation.phase, frozenset()):
        session.rollback()
        raise UpdateProtocolError("illegal_transition")
    if operation.phase == "preparing" and body.phase == "expired":
        if (
            operation.authorization_deadline is None
            or now < operation.authorization_deadline
            or occurred_at < operation.authorization_deadline
            or operation.mutation_started_at is not None
        ):
            session.rollback()
            raise UpdateProtocolError("illegal_transition")
    if body.phase == "recovering" and operation.phase != "needs_intervention":
        if operation.mutation_started_at is None:
            session.rollback()
            raise UpdateProtocolError("illegal_transition")
        if operation.phase == "awaiting_confirmation":
            session.rollback()
            raise UpdateProtocolError("illegal_transition")
    if body.phase == "recovering" and operation.error_code is not None:
        if body.error_code != operation.error_code:
            session.rollback()
            raise UpdateProtocolError("invalid_event_combination", 422)
    if operation.phase == "preparing" and body.phase == "installing":
        if (
            operation.authorization_deadline is None
            or occurred_at > operation.authorization_deadline
        ):
            session.rollback()
            raise UpdateProtocolError("authorization_expired", 410)
        operation.mutation_started_at = occurred_at

    if body.phase == "awaiting_confirmation":
        if (
            body.local_outcome != "succeeded"
            or body.invocation_id is None
            or body.observed_version != operation.target_version
            or body.package_version != operation.target_package_version
            or body.evidence is None
            or body.evidence.package_status != "configured"
            or body.evidence.service_active is not True
            or body.evidence.health_check != "passed"
        ):
            session.rollback()
            raise UpdateProtocolError("local_health_evidence_required")
        operation.invocation_id = body.invocation_id
        operation.local_completed_at = now
    elif body.phase == "succeeded":
        session.rollback()
        raise UpdateProtocolError("hello_confirmation_required")
    elif body.phase == "failed" and operation.mutation_started_at is not None:
        session.rollback()
        raise UpdateProtocolError("recovery_required")

    operation.phase = body.phase
    operation.local_outcome = body.local_outcome
    operation.observed_version = body.observed_version
    operation.observed_package_version = body.package_version
    if body.error_code is not None and (
        operation.error_code is None or body.phase != "needs_intervention"
    ):
        operation.error_code = body.error_code
    operation.last_contact_at = now
    operation.updated_at = now
    evidence = body.evidence.model_dump(exclude_none=True) if body.evidence else None
    session.add(
        AgentUpdateEvent(
            update_id=update_id,
            sequence=body.sequence,
            body_digest=digest,
            phase=body.phase,
            local_outcome=body.local_outcome,
            observed_version=body.observed_version,
            observed_package_version=body.package_version,
            invocation_id=body.invocation_id,
            session_id=body.session_id,
            occurred_at=body.occurred_at,
            error_code=body.error_code,
            evidence_json=evidence,
        )
    )
    if body.phase == "awaiting_confirmation":
        _confirm_if_hello_matches(
            operation,
            agent,
            now=now,
            hello_session_id=current_session_id,
            hello_context=hello_context,
            hello_agent_version=hello_agent_version,
            hello_package_version=hello_package_version,
        )
    session.add(operation)
    session.commit()
    return body.sequence


def reconcile_update_hello(
    session: Session,
    *,
    agent: Agent,
    session_id: UUID,
    update_id: UUID,
    invocation_id: UUID,
    agent_version: str,
    package_version: str | None,
    now: datetime,
) -> None:
    operation = session.exec(
        select(AgentUpdate)
        .where(AgentUpdate.id == update_id, AgentUpdate.agent_id == agent.id)
        .with_for_update()
    ).first()
    if operation is None:
        return
    _confirm_if_hello_matches(
        operation,
        agent,
        now=now,
        hello_session_id=session_id,
        hello_context=(update_id, invocation_id),
        hello_agent_version=agent_version,
        hello_package_version=package_version,
    )
    if operation.phase == "succeeded":
        operation.updated_at = now
        session.add(operation)
