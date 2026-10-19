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

from api.models.command import Agent, Command
from api.models.persistence import ScanRecord, utc_now
from api.schemas.agent_frames import (
    AgentCancelFrame,
    AgentErrorFrame,
    AgentHelloFrame,
    AgentProgressFrame,
    AgentStatusFrame,
    ScanStatusAckFrame,
    UpdateSessionFrame,
)
from api.services import agent_connections
from api.services.agent_presence import SessionFactory, async_agent_is_revoked
from api.services.commands import pending_operator_cancels, transition_command
from api.services.scan_progress import apply_progress


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
class _Progress:
    frame: AgentProgressFrame


@dataclass(frozen=True)
class _Reject:
    message: str


_Parsed = _Hello | _Status | _Progress | _Reject


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

    if frame_type == "progress":
        try:
            return _Progress(AgentProgressFrame.model_validate(data))
        except ValidationError:
            return _Reject("invalid progress frame")

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
) -> tuple[Literal["ok", "unknown_command", "revoked"], str | None, bool]:
    def sync_work() -> tuple[
        Literal["ok", "unknown_command", "revoked"], str | None, bool
    ]:
        session = session_factory()
        try:
            agent = session.exec(
                select(Agent).where(Agent.id == agent_id).with_for_update()
            ).first()
            if agent is None:
                session.rollback()
                return "unknown_command", None, False
            if agent.revoked_at is not None:
                session.rollback()
                return "revoked", None, False
            agent.last_seen_at = now
            transition_command(
                session,
                agent_id=agent_id,
                command_id=frame.command_id,
                status=frame.status,
                now=now,
                error_code=frame.error_code,
            )
            command = session.exec(
                select(Command).where(
                    Command.id == frame.command_id,
                    Command.agent_id == agent_id,
                )
            ).first()
            if command is None:
                session.commit()
                return "unknown_command", None, False
            scan = (
                session.get(ScanRecord, command.scan_id)
                if command.scan_id is not None
                else None
            )
            status = command.status
            has_results = scan is not None and scan.status == "completed"
            session.commit()
            return "ok", status, has_results
        finally:
            session.close()

    return await run_in_threadpool(sync_work)


async def _apply_progress_frame(
    session_factory: SessionFactory,
    *,
    agent_id: UUID,
    frame: AgentProgressFrame,
    now: datetime,
) -> Literal["ok", "unknown_command", "revoked"]:
    def sync_work() -> Literal["ok", "unknown_command", "revoked"]:
        session = session_factory()
        try:
            agent = session.exec(
                select(Agent).where(Agent.id == agent_id).with_for_update()
            ).first()
            if agent is None:
                session.rollback()
                return "unknown_command"
            if agent.revoked_at is not None:
                session.rollback()
                return "revoked"
            agent.last_seen_at = now
            result = apply_progress(
                session,
                agent_id=agent_id,
                frame=frame,
                now=now,
                commit=False,
            )
            session.commit()
            return result
        finally:
            session.close()

    return await run_in_threadpool(sync_work)


def _hello_gate(
    session_factory: SessionFactory,
    agent_id: UUID,
    *,
    session_id: UUID,
    agent_version: str,
    package_version: str | None,
    now: datetime,
) -> tuple[Literal["ok", "revoked"], list[UUID]]:
    session = session_factory()
    try:
        agent = session.exec(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        ).first()
        if agent is None:
            session.rollback()
            return "revoked", []
        if agent.revoked_at is not None:
            session.rollback()
            return "revoked", []
        agent.last_seen_at = now
        agent.observed_version = agent_version
        if package_version is not None:
            agent.observed_package_version = package_version
        agent.version_observed_at = now
        agent.version_observed_session_id = session_id
        pending_cancels = pending_operator_cancels(session, agent_id=agent_id, now=now)
        session.commit()
        return "ok", pending_cancels
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
    async with agent_connections.device_guard(agent_id):
        connection = agent_connections.get_connection(agent_id)
        if connection is None or connection.websocket is not websocket:
            return

        parsed = _parse_frame(raw_text)
        if isinstance(parsed, _Reject):
            await send_error(websocket, parsed.message)
            if await async_agent_is_revoked(session_factory, agent_id):
                await agent_connections.close_revoked(websocket)
            return

        if isinstance(parsed, _Hello):
            gate, pending_cancels = await run_in_threadpool(
                _hello_gate,
                session_factory,
                agent_id,
                session_id=connection.session_id,
                agent_version=parsed.frame.agent_version,
                package_version=parsed.frame.package_version,
                now=now,
            )
            if gate == "revoked":
                await agent_connections.close_revoked(websocket)
                return
            agent_connections.set_hello_locked(
                agent_id,
                websocket,
                agent_version=parsed.frame.agent_version,
                available_subnets=parsed.frame.available_subnets,
                package_version=parsed.frame.package_version,
                capabilities=frozenset(parsed.frame.capabilities),
                now=now,
            )
            if "scan_finalization_v1" in connection.capabilities:
                await websocket.send_text(
                    UpdateSessionFrame(
                        type="update_session",
                        session_id=connection.session_id,
                        protocol_version=1,
                        capabilities=["scan_finalization_v1"],
                    ).model_dump_json()
                )
            await _send_pending_cancels(websocket, agent_id, pending_cancels)
            return

        if isinstance(parsed, _Progress):
            outcome = await _apply_progress_frame(
                session_factory, agent_id=agent_id, frame=parsed.frame, now=now
            )
            if outcome == "revoked":
                await agent_connections.close_revoked(websocket)
                return
            agent_connections.touch_locked(agent_id, websocket, now=now)
            if outcome == "unknown_command":
                await send_error(websocket, "unknown command_id")
            return

        outcome, status, has_results = await _apply_status_frame(
            session_factory, agent_id=agent_id, frame=parsed.frame, now=now
        )
        if outcome == "revoked":
            await agent_connections.close_revoked(websocket)
            return
        agent_connections.touch_locked(agent_id, websocket, now=now)
        if outcome == "unknown_command":
            await send_error(websocket, "unknown command_id")
            return
        if (
            status in {"done", "failed", "cancelled", "expired"}
            and "scan_finalization_v1" in connection.capabilities
        ):
            await websocket.send_text(
                ScanStatusAckFrame(
                    type="scan_status_ack",
                    session_id=connection.session_id,
                    command_id=parsed.frame.command_id,
                    status=status,
                    has_results=has_results,
                ).model_dump_json()
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
