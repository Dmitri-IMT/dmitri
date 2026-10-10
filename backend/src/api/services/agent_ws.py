from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ValidationError
from sqlmodel import select
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from api.models.command import Command
from api.models.persistence import utc_now
from api.schemas.agent_frames import (
    AgentCancelFrame,
    AgentErrorFrame,
    AgentHelloFrame,
    AgentStatusFrame,
)
from api.services import agent_connections
from api.services.agent_presence import (
    SessionFactory,
    async_agent_is_revoked,
    touch_unless_revoked,
)
from api.services.commands import apply_status, pending_operator_cancels


async def send_error(websocket: WebSocket, message: str) -> None:
    frame = AgentErrorFrame(type="error", message=message)
    await websocket.send_text(frame.model_dump_json())


@dataclass(frozen=True)
class _Hello:
    frame: AgentHelloFrame


@dataclass(frozen=True)
class _Status:
    frame: AgentStatusFrame


@dataclass(frozen=True)
class _Reject:
    message: str


_Parsed = _Hello | _Status | _Reject


def _parse_frame(raw_text: str) -> _Parsed:
    """Pure: text in, one of three outcomes out. No I/O, no revocation."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return _Reject("invalid JSON")

    if not isinstance(data, dict):
        return _Reject("invalid frame")

    frame_type = data.get("type")
    if frame_type == "hello":
        try:
            return _Hello(AgentHelloFrame.model_validate(data))
        except ValidationError:
            return _Reject("invalid hello frame")

    if frame_type == "status":
        try:
            return _Status(AgentStatusFrame.model_validate(data))
        except ValidationError:
            return _Reject("invalid status frame")

    if frame_type == "command":
        return _Reject("invalid inbound frame")

    if frame_type is None:
        return _Reject("missing type")

    return _Reject("unknown frame type")


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
            if touch_unless_revoked(session, agent_id, now) == "revoked":
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


def _hello_gate(
    session_factory: SessionFactory, agent_id: UUID, now: datetime
) -> tuple[Literal["ok", "revoked"], list[UUID]]:
    """Touch presence and collect the cancels the Pi missed, in one session."""
    session = session_factory()
    try:
        if touch_unless_revoked(session, agent_id, now) == "revoked":
            return "revoked", []
        return "ok", pending_operator_cancels(session, agent_id=agent_id, now=now)
    finally:
        session.close()


async def _send_pending_cancels(
    websocket: WebSocket, agent_id: UUID, command_ids: list[UUID]
) -> None:
    for command_id in command_ids:
        # A newer connection for this agent owns the catch-up from here.
        if agent_connections.get_socket(agent_id) is not websocket:
            return
        frame = AgentCancelFrame(type="cancel", command_id=command_id)
        await websocket.send_text(frame.model_dump_json())


async def handle_agent_frame(
    session_factory: SessionFactory,
    websocket: WebSocket,
    *,
    agent_id: UUID,
    raw_text: str,
    now: datetime,
) -> None:
    parsed = _parse_frame(raw_text)

    if isinstance(parsed, _Reject):
        # Error frame first, so the Pi can read why, then one revocation query.
        # A healthy agent's malformed frame leaves the socket open.
        await send_error(websocket, parsed.message)
        if await async_agent_is_revoked(session_factory, agent_id):
            await agent_connections.close_revoked(websocket)
        return

    if isinstance(parsed, _Hello):
        # Gate before set_hello: a revoked device must not refresh the subnets
        # the registry feeds to AgentDetail and the trigger-time subnet check.
        gate, pending_cancels = await run_in_threadpool(
            _hello_gate, session_factory, agent_id, now
        )
        if gate == "revoked":
            await agent_connections.close_revoked(websocket)
            return
        await agent_connections.set_hello(
            agent_id,
            websocket,
            agent_version=parsed.frame.agent_version,
            available_subnets=parsed.frame.available_subnets,
            now=now,
        )
        await _send_pending_cancels(websocket, agent_id, pending_cancels)
        return

    outcome = await _apply_status_frame(
        session_factory, agent_id=agent_id, frame=parsed.frame, now=now
    )
    if outcome == "revoked":
        await agent_connections.close_revoked(websocket)
        return
    await agent_connections.touch(agent_id, websocket, now=now)
    if outcome == "unknown_command":
        await send_error(websocket, "unknown command_id")


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
