from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlmodel import select
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket

from api.models.command import Command
from api.models.persistence import utc_now
from api.schemas.agent_frames import AgentErrorFrame, AgentHelloFrame, AgentStatusFrame
from api.services import agent_connections
from api.services.agent_presence import (
    SessionFactory,
    async_touch_agent_last_seen,
    touch_agent_last_seen,
)
from api.services.commands import apply_status


async def send_error(websocket: WebSocket, message: str) -> None:
    frame = AgentErrorFrame(type="error", message=message)
    await websocket.send_text(frame.model_dump_json())


async def _apply_status_frame(
    session_factory: SessionFactory,
    *,
    agent_id: UUID,
    frame: AgentStatusFrame,
    now: datetime,
) -> bool:
    def sync_work() -> bool:
        session = session_factory()
        try:
            applied = apply_status(
                session,
                agent_id=agent_id,
                command_id=frame.command_id,
                status=frame.status,
                now=now,
                error_code=frame.error_code,
            )
            unknown = False
            if not applied:
                exists = (
                    session.exec(
                        select(Command.id).where(
                            Command.id == frame.command_id,
                            Command.agent_id == agent_id,
                        )
                    ).first()
                    is not None
                )
                unknown = not exists
            touch_agent_last_seen(session, agent_id, now)
            return unknown
        finally:
            session.close()

    return await run_in_threadpool(sync_work)


async def handle_agent_frame(
    session_factory: SessionFactory,
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
        await async_touch_agent_last_seen(session_factory, agent_id, now)
        return

    if frame_type == "status":
        try:
            frame = AgentStatusFrame.model_validate(data)
        except ValidationError:
            await send_error(websocket, "invalid status frame")
            return
        await agent_connections.touch(agent_id, websocket, now=now)
        unknown = await _apply_status_frame(
            session_factory, agent_id=agent_id, frame=frame, now=now
        )
        if unknown:
            await send_error(websocket, "unknown command_id")
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
    session_factory: SessionFactory,
    *,
    agent_id: UUID,
) -> None:
    async for raw_text in websocket.iter_text():
        await handle_agent_frame(
            session_factory,
            websocket,
            agent_id=agent_id,
            raw_text=raw_text,
            now=utc_now(),
        )
