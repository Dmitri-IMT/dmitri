from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent
from api.dependencies.auth import CallerIdentity, require_admin, require_user
from api.errors import ApiError
from api.schemas.agent_updates import (
    AgentProtocolSupport,
    AgentUpdateAvailability,
    AgentUpdateClaimReceipt,
    AgentUpdateClaimRequest,
    AgentUpdateEventAck,
    AgentUpdateEventRequest,
    AgentUpdateHistoryPage,
    AgentUpdateRequest,
    UpdateConflictResponse,
    UpdateForbiddenResponse,
    UpdateOperationView,
    UpdateProtocolErrorResponse,
    UpdateUnauthorizedResponse,
    UpdateUnavailableResponse,
)
from api.services import agent_connections
from api.services.agent_updates import (
    UpdateProtocolError,
    claim_update,
    record_update_event,
)
from api.services.agent_updates_http import (
    UpdateAdmissionError,
    read_availability,
    read_history,
    read_operation,
    request_update,
)

router = APIRouter()


def _raise_update_protocol_error(exc: UpdateProtocolError) -> None:
    messages = {
        "not_found": "Update operation not found.",
        "device_revoked": "The device is revoked.",
        "release_not_allowed": "The release is not allowed.",
        "artifact_mismatch": "The claimed artifact does not match the release.",
        "session_replaced": "The update session is no longer current.",
        "request_expired": "The update request has expired.",
        "authorization_expired": "The update authorization has expired.",
        "claim_state_invalid": "The update claim is invalid.",
        "illegal_transition": "The update transition is not allowed.",
        "sequence_conflict": (
            "The event sequence was already used with different content."
        ),
        "sequence_out_of_order": "The next event sequence is required.",
        "claim_required": "A valid update claim is required.",
        "local_health_evidence_required": "Local health evidence is required.",
        "hello_confirmation_required": "A current hello is required for confirmation.",
        "recovery_required": "A recovery event is required after mutation failure.",
        "invalid_event_time": "The event time is invalid.",
        "invalid_event_combination": "Event phase, outcome, and evidence do not match.",
    }
    raise ApiError(
        exc.status,
        messages.get(exc.code, "Update event rejected."),
        code=exc.code,
    ) from exc


@router.post(
    "/api/v1/agent-updates/{update_id}/claim",
    response_model=AgentUpdateClaimReceipt,
    operation_id="claimAgentUpdate",
    responses={
        401: {"description": "Invalid device signature"},
        403: {"description": "Device revoked"},
        404: {"description": "Update not found"},
        409: {"model": UpdateProtocolErrorResponse, "description": "Claim rejected"},
        410: {"model": UpdateProtocolErrorResponse, "description": "Claim expired"},
    },
)
async def post_agent_update_claim(
    update_id: UUID,
    body: AgentUpdateClaimRequest,
    identity: AgentIdentity = Depends(require_agent),
    session: Session = Depends(get_session),
) -> AgentUpdateClaimReceipt:
    async with agent_connections.device_guard(identity.agent_id):
        connection = agent_connections.get_connection(identity.agent_id)
        current_session_id = (
            connection.session_id
            if connection is not None and "agent_update_v1" in connection.capabilities
            else None
        )
        try:
            return await run_in_threadpool(
                claim_update,
                session,
                agent_id=identity.agent_id,
                update_id=update_id,
                body=body,
                current_session_id=current_session_id,
                now=datetime.now(UTC),
            )
        except UpdateProtocolError as exc:
            _raise_update_protocol_error(exc)


@router.post(
    "/api/v1/agent-updates/{update_id}/events",
    response_model=AgentUpdateEventAck,
    operation_id="reportAgentUpdateEvent",
    responses={
        401: {"description": "Invalid device signature"},
        403: {"description": "Device revoked"},
        404: {"description": "Update not found"},
        409: {"model": UpdateProtocolErrorResponse, "description": "Event rejected"},
        410: {
            "model": UpdateProtocolErrorResponse,
            "description": "Authorization expired",
        },
        422: {"description": "Invalid event"},
    },
)
async def post_agent_update_event(
    update_id: UUID,
    body: AgentUpdateEventRequest,
    identity: AgentIdentity = Depends(require_agent),
    session: Session = Depends(get_session),
) -> AgentUpdateEventAck:
    async with agent_connections.device_guard(identity.agent_id):
        connection = agent_connections.get_connection(identity.agent_id)
        has_current_update_hello = bool(
            connection is not None and "agent_update_v1" in connection.capabilities
        )
        try:
            sequence = await run_in_threadpool(
                record_update_event,
                session,
                agent_id=identity.agent_id,
                update_id=update_id,
                body=body,
                now=datetime.now(UTC),
                current_session_id=(connection.session_id if connection else None),
                hello_context=(
                    (
                        connection.update_context.update_id,
                        connection.update_context.invocation_id,
                    )
                    if has_current_update_hello
                    and connection.update_context is not None
                    else None
                ),
                hello_agent_version=connection.agent_version
                if has_current_update_hello
                else None,
                hello_package_version=connection.package_version
                if has_current_update_hello
                else None,
            )
            return AgentUpdateEventAck(ack_sequence=sequence)
        except UpdateProtocolError as exc:
            _raise_update_protocol_error(exc)


@router.get(
    "/api/v1/agents/{agent_id}/update-protocol",
    response_model=AgentProtocolSupport,
    operation_id="getAgentUpdateProtocol",
)
def read_agent_update_protocol(
    agent_id: UUID,
    identity: AgentIdentity = Depends(require_agent),
) -> AgentProtocolSupport:
    if identity.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentProtocolSupport(
        protocol_versions=[1],
        capabilities=["scan_finalization_v1", "agent_update_v1"],
    )


@router.get(
    "/api/v1/agents/{agent_id}/updates/availability",
    response_model=AgentUpdateAvailability,
    operation_id="getAgentUpdateAvailability",
)
def get_update_availability(
    agent_id: UUID,
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> AgentUpdateAvailability:
    result = read_availability(
        session, agent_id=agent_id, org_id=caller.org_id, now=datetime.now(UTC)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.get(
    "/api/v1/agents/{agent_id}/updates",
    response_model=AgentUpdateHistoryPage,
    operation_id="listAgentUpdates",
)
def list_agent_updates(
    agent_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: UUID | None = Query(default=None),
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> AgentUpdateHistoryPage:
    result = read_history(
        session,
        agent_id=agent_id,
        org_id=caller.org_id,
        limit=limit,
        cursor=cursor,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.get(
    "/api/v1/agent-updates/{update_id}",
    response_model=UpdateOperationView,
    operation_id="getAgentUpdate",
)
def get_agent_update(
    update_id: UUID,
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> UpdateOperationView:
    result = read_operation(session, update_id=update_id, org_id=caller.org_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Update not found")
    return result


@router.post(
    "/api/v1/agents/{agent_id}/updates",
    response_model=UpdateOperationView,
    operation_id="requestAgentUpdate",
    responses={
        202: {"model": UpdateOperationView},
        401: {"model": UpdateUnauthorizedResponse},
        403: {"model": UpdateForbiddenResponse},
        409: {"model": UpdateConflictResponse},
        503: {"model": UpdateUnavailableResponse},
    },
)
async def request_agent_update(
    agent_id: UUID,
    body: AgentUpdateRequest,
    response: Response,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UpdateOperationView:
    try:
        operation, created = await request_update(
            session,
            agent_id=agent_id,
            org_id=caller.org_id,
            actor_id=caller.sub,
            idempotency_key=idempotency_key,
            release_id=body.release_id,
            expected_version=body.expected_observed_version,
            now=datetime.now(UTC),
        )
    except UpdateAdmissionError as exc:
        messages = {
            "idempotency_conflict": "Idempotency key conflicts with earlier use.",
            "device_busy": "The device is busy.",
            "version_conflict": "The observed device version changed.",
            "release_not_allowed": "The release is not available for this device.",
            "device_offline": "The device is offline.",
            "device_revoked": "The device is revoked.",
            "bootstrap_required": "The device requires update support.",
            "release_check_unavailable": "Release metadata is unavailable.",
            "forbidden": "Admin role required.",
            "unauthorized": "Not authenticated.",
            "not_found": "Agent not found.",
        }
        raise ApiError(exc.status, messages[exc.code], code=exc.code) from exc
    response.status_code = 202 if created else 200
    response.headers["Location"] = f"/api/v1/agent-updates/{operation.update_id}"
    return operation


@router.options("/api/v1/agents/{agent_id}/updates", status_code=204)
def options_agent_updates() -> None:
    return None


@router.options("/api/v1/agents/{agent_id}/updates/availability", status_code=204)
def options_agent_update_availability() -> None:
    return None


@router.options("/api/v1/agent-updates/{update_id}", status_code=204)
def options_agent_update() -> None:
    return None
