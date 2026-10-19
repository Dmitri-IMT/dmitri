from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent_ws
from api.dependencies.auth import CallerIdentity, require_admin, require_user
from api.errors import ApiError
from api.models.command import Command
from api.models.identity import Org
from api.models.persistence import utc_now
from api.schemas.agents import (
    AgentDetail,
    AgentListResponse,
    RegisterAgentRequest,
    RegisterAgentResponse,
    UpdateAgentTargetSubnetRequest,
)
from api.schemas.commands import CommandSummary, CreateCommandRequest
from api.services import agent_connections, commands
from api.services.agent_presence import (
    async_mark_connected,
    async_mark_disconnected,
    default_session_factory,
)
from api.services.agent_ws import run_agent_channel
from api.services.agents import (
    AgentOfflineError,
    get_agent_detail,
    list_agents,
    register_agent,
    restore_agent,
    revoke_agent,
    set_target_subnet,
)

router = APIRouter()


def _command_summary(command: Command) -> CommandSummary:
    return CommandSummary(
        command_id=command.id,
        scan_id=command.scan_id,
        agent_id=command.agent_id,
        status=command.status,
    )


@router.get("/api/v1/agents", response_model=AgentListResponse)
def list_agents_route(
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> AgentListResponse:
    return AgentListResponse(data=list_agents(session, org_id=caller.org_id))


@router.post(
    "/api/v1/agents",
    response_model=RegisterAgentResponse,
    status_code=201,
)
def register_agent_route(
    body: RegisterAgentRequest,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> RegisterAgentResponse:
    agent = register_agent(
        session,
        org=session.get_one(Org, caller.org_id),
        display_name=body.display_name,
        public_key=bytes.fromhex(body.public_key),
    )
    return RegisterAgentResponse(agent_id=agent.id)


@router.options("/api/v1/agents", status_code=204)
def options_agents() -> None:
    return None


@router.get("/api/v1/agents/{agent_id}", response_model=AgentDetail)
def read_agent_route(
    agent_id: UUID,
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> AgentDetail:
    detail = get_agent_detail(session, agent_id=agent_id, org_id=caller.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@router.patch("/api/v1/agents/{agent_id}", response_model=AgentDetail)
def update_agent_target_subnet_route(
    agent_id: UUID,
    body: UpdateAgentTargetSubnetRequest,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AgentDetail:
    try:
        detail = set_target_subnet(
            session,
            agent_id=agent_id,
            org_id=caller.org_id,
            target_subnet=body.target_subnet,
        )
    except AgentOfflineError as exc:
        raise ApiError(409, "Pi seems to be offline.", code="device_offline") from exc
    except commands.SubnetNotReportedError as exc:
        raise ApiError(
            422,
            "That network is not one the Pi reported.",
            code="subnet_not_reported",
        ) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@router.options("/api/v1/agents/{agent_id}", status_code=204)
def options_agent() -> None:
    return None


@router.post("/api/v1/agents/{agent_id}/revoke", response_model=AgentDetail)
async def revoke_agent_route(
    agent_id: UUID,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AgentDetail:
    detail = await revoke_agent(
        session, agent_id=agent_id, org_id=caller.org_id, now=utc_now()
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@router.post("/api/v1/agents/{agent_id}/restore", response_model=AgentDetail)
def restore_agent_route(
    agent_id: UUID,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AgentDetail:
    detail = restore_agent(session, agent_id=agent_id, org_id=caller.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@router.post(
    "/api/v1/agents/{agent_id}/commands",
    response_model=CommandSummary,
    status_code=201,
)
async def create_agent_command(
    agent_id: UUID,
    body: CreateCommandRequest,
    caller: CallerIdentity = Depends(require_admin),
    session: Session = Depends(get_session),
) -> CommandSummary:
    try:
        command = await commands.enqueue_for_agent(
            session,
            org_id=caller.org_id,
            agent_id=agent_id,
            scan_mode=body.scan_mode,
            subnet=body.subnet,
            nspi_options=(
                body.nspi_options.model_dump()
                if body.nspi_options is not None
                else None
            ),
            now=utc_now(),
        )
    except commands.AgentNotFoundError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except commands.DeviceBusyError as exc:
        raise ApiError(
            409, "That Pi is already scanning.", code="device_busy"
        ) from exc
    except commands.SubnetNotReportedError as exc:
        raise ApiError(
            422, "That network is not one the Pi reported.", code="subnet_not_reported"
        ) from exc
    except commands.DeviceOfflineError as exc:
        raise ApiError(503, "Pi seems to be offline.", code="device_offline") from exc

    return _command_summary(command)


@router.websocket("/api/v1/agents/{agent_id}/commands")
async def connect_agent_commands(
    websocket: WebSocket,
    agent_id: UUID,
    identity: AgentIdentity = Depends(require_agent_ws),
) -> None:
    await websocket.accept()
    now = utc_now()
    async with agent_connections.device_guard(identity.agent_id):
        await agent_connections.register_locked(identity.agent_id, websocket, now=now)
        await async_mark_connected(default_session_factory, identity.agent_id, now)
    try:
        await run_agent_channel(
            websocket, default_session_factory, agent_id=identity.agent_id
        )
    finally:
        async with agent_connections.device_guard(identity.agent_id):
            if agent_connections.unregister_locked(identity.agent_id, websocket):
                await async_mark_disconnected(
                    default_session_factory, identity.agent_id
                )


def agent_commands_preflight() -> None:
    return None


router.add_api_route(
    "/api/v1/agents/{agent_id}/commands",
    agent_commands_preflight,
    methods=["OPTIONS"],
    status_code=204,
)
