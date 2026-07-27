from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent_ws
from api.models.persistence import utc_now
from api.services import agent_connections
from api.services.agent_ws import run_agent_channel, touch_agent_last_seen

router = APIRouter()


@router.websocket("/api/v1/agents/{agent_id}/commands")
async def connect_agent_commands(
    websocket: WebSocket,
    agent_id: UUID,
    identity: AgentIdentity = Depends(require_agent_ws),
    session: Session = Depends(get_session),
) -> None:
    await websocket.accept()
    now = utc_now()
    await agent_connections.register(identity.agent_id, websocket, now=now)
    touch_agent_last_seen(session, identity.agent_id, now)
    try:
        await run_agent_channel(websocket, session, agent_id=identity.agent_id)
    finally:
        await agent_connections.unregister(identity.agent_id, websocket, now=utc_now())
