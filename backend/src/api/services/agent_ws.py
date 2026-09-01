from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ValidationError
from sqlmodel import select
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from api.models.command import Command
from api.models.persistence import utc_now
from api.schemas.agent_frames import AgentErrorFrame, AgentHelloFrame, AgentStatusFrame
from api.services import agent_connections
from api.services.agent_presence import (
    SessionFactory,
    agent_is_revoked,
    async_touch_unless_revoked,
    touch_unless_revoked,
)
from api.services.commands import apply_status


async def send_error(websocket: WebSocket, message: str) -> None:
    frame = AgentErrorFrame(type="error", message=message)
    await websocket.send_text(frame.model_dump_json())


async def _reject_frame(
    session_factory: SessionFactory,
    websocket: WebSocket,
    *,
    agent_id: UUID,
    message: str,
) -> None:
    await send_error(websocket, message)

    def sync_work() -> bool:
        session = session_factory()
        try:
            return agent_is_revoked(session, agent_id)
        finally:
            session.close()

    if await run_in_threadpool(sync_work):
        await agent_connections.close_revoked(websocket)


async def _apply_status_frame(
    session_factory: SessionFactory,
    *,
    agent_id: UUID,
    frame: AgentStatusFrame,
    now: datetime,
) -> Literal["ok", "unknown_command", "revoked"]:
    def sync_work() -> Literal["ok", "unknown_command", "revoked"]:
        session = session_factory()
        try:
            if touch_unless_revoked(session, agent_id, now):
                return "revoked"
            applied = apply_status(
                session,
                agent_id=agent_id,
                command_id=frame.command_id,
                status=frame.status,
                now=now,
                error_code=frame.error_code,
            )
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
                if not exists:
                    return "unknown_command"
            return "ok"
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
        await _reject_frame(
            session_factory, websocket, agent_id=agent_id, message="invalid JSON"
        )
        return

    if not isinstance(data, dict):
        await _reject_frame(
            session_factory, websocket, agent_id=agent_id, message="invalid frame"
        )
        return

    frame_type = data.get("type")
    if frame_type == "hello":
        try:
            frame = AgentHelloFrame.model_validate(data)
        except ValidationError:
            await _reject_frame(
                session_factory,
                websocket,
                agent_id=agent_id,
                message="invalid hello frame",
            )
            return
        if await async_touch_unless_revoked(session_factory, agent_id, now):
            await agent_connections.close_revoked(websocket)
            return
        await agent_connections.set_hello(
            agent_id,
            websocket,
            agent_version=frame.agent_version,
            available_subnets=frame.available_subnets,
            now=now,
        )
        return

    if frame_type == "status":
        try:
            frame = AgentStatusFrame.model_validate(data)
        except ValidationError:
            await _reject_frame(
                session_factory,
                websocket,
                agent_id=agent_id,
                message="invalid status frame",
            )
            return
        outcome = await _apply_status_frame(
            session_factory, agent_id=agent_id, frame=frame, now=now
        )
        if outcome == "revoked":
            await agent_connections.close_revoked(websocket)
            return
        await agent_connections.touch(agent_id, websocket, now=now)
        if outcome == "unknown_command":
            await send_error(websocket, "unknown command_id")
        return

    if frame_type == "command":
        await _reject_frame(
            session_factory,
            websocket,
            agent_id=agent_id,
            message="invalid inbound frame",
        )
        return

    if frame_type is None:
        await _reject_frame(
            session_factory, websocket, agent_id=agent_id, message="missing type"
        )
        return

    await _reject_frame(
        session_factory, websocket, agent_id=agent_id, message="unknown frame type"
    )


async def run_agent_channel(
    websocket: WebSocket,
    session_factory: SessionFactory,
    *,
    agent_id: UUID,
) -> None:
    while websocket.application_state == WebSocketState.CONNECTED:
        # Not `iter_text()`: it only swallows WebSocketDisconnect. When a second
        # connection for this agent arrives, `agent_connections.register()`
        # closes this socket from under the loop, and the next `receive_text()`
        # raises a bare RuntimeError instead. Whether the displaced handler was
        # parked inside `receive()` (clean disconnect) or at the loop boundary
        # (RuntimeError) is pure scheduling luck, so check the state ourselves.
        # Being replaced is a normal end of life, not an error.
        try:
            raw_text = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        await handle_agent_frame(
            session_factory,
            websocket,
            agent_id=agent_id,
            raw_text=raw_text,
            now=utc_now(),
        )
