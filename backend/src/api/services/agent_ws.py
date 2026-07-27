from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlmodel import Session
from starlette.websockets import WebSocket

from api.models.command import Agent
from api.models.persistence import utc_now
from api.schemas.agent_frames import AgentErrorFrame, AgentHelloFrame, AgentStatusFrame
from api.services import agent_connections


async def send_error(websocket: WebSocket, message: str) -> None:
    frame = AgentErrorFrame(type="error", message=message)
    await websocket.send_text(frame.model_dump_json())


def touch_agent_last_seen(session: Session, agent_id: UUID, now: datetime) -> None:
    agent = session.get(Agent, agent_id)
    if agent is None:
        return
    agent.last_seen_at = now
    session.commit()


async def handle_agent_frame(
    session: Session,
    websocket: WebSocket,
    *,
    agent_id: UUID,
    raw_text: str,
    now: datetime,
) -> None:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        await send_error(websocket, "invalid JSON")
        return

    if not isinstance(data, dict):
        await send_error(websocket, "invalid frame")
        return

    frame_type = data.get("type")
    if frame_type == "hello":
        try:
            frame = AgentHelloFrame.model_validate(data)
        except ValidationError:
            await send_error(websocket, "invalid hello frame")
            return
        await agent_connections.set_hello(
            agent_id,
            websocket,
            agent_version=frame.agent_version,
            available_subnets=frame.available_subnets,
            now=now,
        )
        touch_agent_last_seen(session, agent_id, now)
        return

    if frame_type == "status":
        try:
            AgentStatusFrame.model_validate(data)
        except ValidationError:
            await send_error(websocket, "invalid status frame")
            return
        await agent_connections.touch(agent_id, websocket, now=now)
        touch_agent_last_seen(session, agent_id, now)
        return

    if frame_type == "command":
        await send_error(websocket, "invalid inbound frame")
        return

    if frame_type is None:
        await send_error(websocket, "missing type")
        return

    await send_error(websocket, "unknown frame type")


async def run_agent_channel(
    websocket: WebSocket,
    session: Session,
    *,
    agent_id: UUID,
) -> None:
    async for raw_text in websocket.iter_text():
        await handle_agent_frame(
            session,
            websocket,
            agent_id=agent_id,
            raw_text=raw_text,
            now=utc_now(),
        )
