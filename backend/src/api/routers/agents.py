from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent_ws
from api.dependencies.auth import CallerIdentity, require_admin
from api.errors import ApiError
from api.models.command import Command
from api.models.persistence import utc_now
from api.schemas.commands import CommandSummary, CreateCommandRequest
from api.services import agent_connections, commands
from api.services.agent_presence import (
    async_mark_connected,
    async_mark_disconnected,
    default_session_factory,
)
from api.services.agent_ws import run_agent_channel

router = APIRouter()


def _command_summary(command: Command) -> CommandSummary:
    return CommandSummary(
        command_id=command.id,
        scan_id=command.scan_id,
        agent_id=command.agent_id,
        status=command.status,
    )


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
            now=utc_now(),
        )
    except commands.AgentNotFoundError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except commands.DeviceBusyError as exc:
        raise ApiError(
            409, "That Pi is already scanning.", code="device_busy"
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
    await agent_connections.register(identity.agent_id, websocket, now=now)
    await async_mark_connected(default_session_factory, identity.agent_id, now)
    try:
        await run_agent_channel(
            websocket, default_session_factory, agent_id=identity.agent_id
        )
    finally:
        await agent_connections.unregister(identity.agent_id, websocket, now=utc_now())
        await async_mark_disconnected(default_session_factory, identity.agent_id)


def agent_commands_preflight() -> None:
    return None


router.add_api_route(
    "/api/v1/agents/{agent_id}/commands",
    agent_commands_preflight,
    methods=["OPTIONS"],
    status_code=204,
)
