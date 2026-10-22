from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from uuid import UUID

from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from api.models.agent_update import (
    AgentRelease,
    AgentReleaseCatalogState,
    AgentUpdate,
)
from api.models.command import Agent
from api.models.identity import ROLE_ADMIN, User
from api.schemas.agent_frames import AgentUpdateFrame
from api.schemas.agent_updates import (
    AgentUpdateAvailability,
    AgentUpdateHistoryPage,
    ReleaseSummary,
    UpdateOperationView,
)
from api.services import agent_connections
from api.services.commands import active_command_for
from api.services.release_catalog import (
    debian_version_compare,
    project_availability,
)


class UpdateAdmissionError(Exception):
    def __init__(self, code: str, status: int):
        self.code = code
        self.status = status


def _release_view(release: AgentRelease | None) -> ReleaseSummary | None:
    if release is None:
        return None
    return ReleaseSummary(
        release_id=release.id,
        package=release.package,
        upstream_version=release.upstream_version,
        package_version=release.package_version,
        architecture=release.architecture,
        suite=release.suite,
        sha256=release.sha256,
        size_bytes=release.size_bytes,
        required_protocol_version=release.required_protocol_version,
        required_updater_version=release.required_updater_version,
        published_at=release.published_at,
        release_notes=release.release_notes,
    )


def _operation(row: AgentUpdate) -> UpdateOperationView:
    return UpdateOperationView(
        update_id=row.id,
        agent_id=row.agent_id,
        release_id=row.release_id,
        previous_version=row.previous_version,
        previous_package_version=row.previous_package_version,
        target_version=row.target_version,
        target_package_version=row.target_package_version,
        observed_version=row.observed_version,
        observed_package_version=row.observed_package_version,
        phase=row.phase,
        local_outcome=row.local_outcome,
        error_code=row.error_code,
        actor_display_snapshot=row.actor_display_snapshot,
        requested_at=row.requested_at,
        claimed_at=row.claimed_at,
        local_completed_at=row.local_completed_at,
        confirmed_at=row.confirmed_at,
        last_contact_at=row.last_contact_at,
    )


def read_availability(
    session: Session, *, agent_id: UUID, org_id: UUID, now: datetime
) -> AgentUpdateAvailability | None:
    agent = session.exec(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == org_id)
    ).first()
    if agent is None:
        return None
    connection = agent_connections.get_connection(agent_id)
    busy = active_command_for(session, agent_id) is not None or session.exec(
        select(AgentUpdate.id).where(
            AgentUpdate.agent_id == agent_id,
            AgentUpdate.phase.in_((
                "requested", "preparing", "installing", "verifying",
                "awaiting_confirmation", "recovering", "needs_intervention",
            )),
        )
    ).first() is not None
    if agent.revoked_at is not None:
        readiness = "revoked"
    elif connection is None:
        readiness = "offline"
    elif busy:
        readiness = "busy"
    elif "agent_update_v1" not in connection.capabilities:
        readiness = "bootstrap_required"
    else:
        readiness = "ready"
    state = session.get(AgentReleaseCatalogState, 1)
    releases = session.exec(
        select(AgentRelease).where(
            AgentRelease.approved_at.is_not(None),
            AgentRelease.withdrawn_at.is_(None),
        ).order_by(AgentRelease.published_at.desc())
    ).all()
    architecture = ""
    protocol = updater = None
    if connection is not None:
        architecture = getattr(connection, "architecture", None) or ""
        protocol = connection.protocol_version
        try:
            updater = int(connection.updater_version or "")
        except ValueError:
            updater = None
    availability, release = project_availability(
        releases,
        installed_version=agent.observed_package_version,
        architecture=architecture,
        suite=connection.os_suite if connection else None,
        protocol_version=protocol,
        updater_version=updater,
        catalog_valid_until=state.valid_until if state else None,
        now=now,
    )
    return AgentUpdateAvailability(
        availability=availability,
        release=_release_view(release),
        catalogue_checked_at=state.validated_at if state else None,
        catalogue_valid_until=state.valid_until if state else None,
        device_readiness=readiness,
    )


def read_history(
    session: Session, *, agent_id: UUID, org_id: UUID, limit: int, cursor: UUID | None
) -> AgentUpdateHistoryPage | None:
    agent_exists = session.exec(
        select(Agent.id).where(Agent.id == agent_id, Agent.org_id == org_id)
    ).first()
    if agent_exists is None:
        return None
    query = select(AgentUpdate).where(
        AgentUpdate.agent_id == agent_id, AgentUpdate.org_id == org_id
    )
    if cursor is not None:
        cursor_row = session.exec(
            select(AgentUpdate).where(
                AgentUpdate.id == cursor, AgentUpdate.agent_id == agent_id
            )
        ).first()
        if cursor_row is None:
            return AgentUpdateHistoryPage(data=[])
        query = query.where(
            (AgentUpdate.created_at < cursor_row.created_at)
            | (
                (AgentUpdate.created_at == cursor_row.created_at)
                & (AgentUpdate.id < cursor_row.id)
            )
        )
    rows = session.exec(
        query.order_by(AgentUpdate.created_at.desc(), AgentUpdate.id.desc()).limit(
            limit + 1
        )
    ).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return AgentUpdateHistoryPage(
        data=[_operation(row) for row in rows],
        next_cursor=str(rows[-1].id) if more and rows else None,
    )


def read_operation(
    session: Session, *, update_id: UUID, org_id: UUID
) -> UpdateOperationView | None:
    row = session.exec(
        select(AgentUpdate).where(
            AgentUpdate.id == update_id, AgentUpdate.org_id == org_id
        )
    ).first()
    return _operation(row) if row else None


def _reserve(
    session: Session, *, agent_id: UUID, org_id: UUID, actor_id: UUID,
    idempotency_key: UUID, release_id: UUID, expected_version: str,
    request_digest: str, now: datetime,
) -> tuple[UpdateOperationView, bool, UUID]:
    agent = session.exec(
        select(Agent).where(Agent.id == agent_id).with_for_update()
    ).first()
    if agent is None or agent.org_id != org_id:
        session.rollback()
        raise UpdateAdmissionError("not_found", 404)
    actor = session.exec(
        select(User).where(User.id == actor_id).with_for_update()
    ).first()
    if actor is None or actor.org_id != org_id:
        session.rollback()
        raise UpdateAdmissionError("unauthorized", 401)
    if actor.role != ROLE_ADMIN:
        session.rollback()
        raise UpdateAdmissionError("forbidden", 403)

    prior = session.exec(select(AgentUpdate).where(
        AgentUpdate.org_id == org_id, AgentUpdate.agent_id == agent_id,
        AgentUpdate.idempotency_key == str(idempotency_key),
    )).first()
    if prior:
        prior_view = _operation(prior)
        prior_session_id = prior.session_id
        session.rollback()
        if prior.request_digest != request_digest:
            raise UpdateAdmissionError("idempotency_conflict", 409)
        return prior_view, False, prior_session_id

    if agent.revoked_at is not None:
        session.rollback()
        raise UpdateAdmissionError("device_revoked", 403)
    if agent.observed_version is None or agent.observed_version != expected_version:
        session.rollback()
        raise UpdateAdmissionError("version_conflict", 409)
    catalog = session.get(AgentReleaseCatalogState, 1)
    if catalog is None or catalog.valid_until is None or catalog.valid_until <= now:
        session.rollback()
        raise UpdateAdmissionError("release_check_unavailable", 503)
    release = session.exec(select(AgentRelease).where(
        AgentRelease.id == release_id, AgentRelease.approved_at.is_not(None),
        AgentRelease.withdrawn_at.is_(None),
    )).first()
    if release is None:
        session.rollback()
        raise UpdateAdmissionError("release_not_allowed", 409)
    connection = agent_connections.get_connection(agent_id)
    if connection is None:
        session.rollback()
        raise UpdateAdmissionError("device_offline", 503)
    if agent.version_observed_session_id != connection.session_id:
        session.rollback()
        raise UpdateAdmissionError("bootstrap_required", 503)
    if "agent_update_v1" not in connection.capabilities:
        session.rollback()
        raise UpdateAdmissionError("bootstrap_required", 503)
    if (
        not connection.architecture
        or not connection.os_suite
        or connection.architecture != release.architecture
        or connection.os_suite != release.suite
    ):
        session.rollback()
        raise UpdateAdmissionError("release_not_allowed", 409)
    try:
        updater_version = int(connection.updater_version or "")
    except ValueError:
        session.rollback()
        raise UpdateAdmissionError("bootstrap_required", 503) from None
    if updater_version < release.required_updater_version:
        session.rollback()
        raise UpdateAdmissionError("bootstrap_required", 503)
    if (
        connection.protocol_version is None
        or connection.protocol_version < release.required_protocol_version
    ):
        session.rollback()
        raise UpdateAdmissionError("bootstrap_required", 503)
    active_updates = session.exec(
        select(AgentUpdate.id).where(
            AgentUpdate.agent_id == agent_id,
            AgentUpdate.phase.in_(
                (
                    "requested", "preparing", "installing", "verifying",
                    "awaiting_confirmation", "recovering", "needs_intervention",
                )
            ),
        )
    ).first()
    if active_command_for(session, agent_id) is not None or active_updates is not None:
        session.rollback()
        raise UpdateAdmissionError("device_busy", 409)
    if agent.observed_package_version is None:
        session.rollback()
        raise UpdateAdmissionError("version_conflict", 409)
    try:
        is_upgrade = debian_version_compare(
            release.package_version, "gt", agent.observed_package_version
        )
    except ValueError:
        session.rollback()
        raise UpdateAdmissionError("version_conflict", 409) from None
    if not is_upgrade:
        session.rollback()
        raise UpdateAdmissionError("release_not_allowed", 409)
    operation = AgentUpdate(
        org_id=org_id, agent_id=agent_id, actor_id=actor_id,
        actor_display_snapshot=actor.email[:320], idempotency_key=str(idempotency_key),
        request_digest=request_digest, release_id=release.id,
        previous_version=agent.observed_version,
        previous_package_version=agent.observed_package_version,
        target_version=release.upstream_version,
        target_package_version=release.package_version,
        session_id=connection.session_id, phase="requested",
        claim_deadline=now + timedelta(seconds=30), requested_at=now,
    )
    session.add(operation)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(operation)
    return _operation(operation), True, connection.session_id


async def request_update(
    session: Session, *, agent_id: UUID, org_id: UUID, actor_id: UUID,
    idempotency_key: UUID, release_id: UUID, expected_version: str,
    now: datetime,
) -> tuple[UpdateOperationView, bool]:
    body = {
        "release_id": str(release_id),
        "expected_observed_version": expected_version,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    async with agent_connections.device_guard(agent_id):
        operation, created, session_id = await run_in_threadpool(
            _reserve, session, agent_id=agent_id, org_id=org_id, actor_id=actor_id,
            idempotency_key=idempotency_key, release_id=release_id,
            expected_version=expected_version, request_digest=digest, now=now,
        )
        if not created:
            return operation, False
        connection = agent_connections.get_connection(agent_id)
        if connection is None or connection.session_id != session_id:
            return operation, True
        operation, frame = await run_in_threadpool(
            _delivery_snapshot,
            session,
            agent_id=agent_id,
            session_id=session_id,
            operation_id=operation.update_id,
            now=now,
        )
        if frame is not None:
            try:
                await connection.websocket.send_text(frame.model_dump_json())
            except Exception:
                pass
        return operation, True


def _delivery_snapshot(
    session: Session,
    *,
    agent_id: UUID,
    session_id: UUID,
    operation_id: UUID,
    now: datetime,
) -> tuple[UpdateOperationView, AgentUpdateFrame | None]:
    agent = session.exec(
        select(Agent).where(Agent.id == agent_id).with_for_update()
    ).first()
    connection = agent_connections.get_connection(agent_id)
    operation = session.exec(
        select(AgentUpdate)
        .where(AgentUpdate.id == operation_id, AgentUpdate.agent_id == agent_id)
        .with_for_update()
    ).first()
    release = (
        session.get(AgentRelease, operation.release_id)
        if operation is not None
        else None
    )
    valid = (
        agent is not None
        and agent.revoked_at is None
        and agent.version_observed_session_id == session_id
        and connection is not None
        and connection.session_id == session_id
        and "agent_update_v1" in connection.capabilities
        and connection.protocol_version is not None
        and operation is not None
        and operation.phase == "requested"
        and operation.claim_deadline > now
        and release is not None
        and connection.protocol_version >= release.required_protocol_version
        and connection.architecture == release.architecture
        and connection.os_suite == release.suite
    )
    if operation is None:
        session.rollback()
        raise RuntimeError("reserved update operation disappeared")
    view = _operation(operation)
    frame = (
        AgentUpdateFrame(
            type="agent_update",
            update_id=operation.id,
            session_id=session_id,
            release_id=release.id,
            target_package_version=release.package_version,
            sha256=release.sha256,
            expires_at=operation.claim_deadline,
        )
        if valid and release is not None
        else None
    )
    session.commit()
    return view, frame


def expire_unclaimed_updates(
    session: Session, *, now: datetime, batch_size: int = 100
) -> int:
    candidate_ids = session.exec(
        select(AgentUpdate.id)
        .where(AgentUpdate.phase == "requested", AgentUpdate.claim_deadline <= now)
        .order_by(AgentUpdate.claim_deadline)
        .limit(batch_size)
    ).all()
    expired = 0
    for update_id in candidate_ids:
        candidate = session.get(AgentUpdate, update_id)
        if candidate is None:
            continue
        session.exec(
            select(Agent).where(Agent.id == candidate.agent_id).with_for_update()
        ).first()
        row = session.exec(
            select(AgentUpdate)
            .where(
                AgentUpdate.id == update_id,
                AgentUpdate.phase == "requested",
                AgentUpdate.claim_deadline <= now,
            )
            .with_for_update()
        ).first()
        if row is None:
            session.rollback()
            continue
        row.phase = "expired"
        row.error_code = "request_expired"
        row.updated_at = now
        session.add(row)
        session.commit()
        expired += 1
    return expired
