from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from starlette.websockets import WebSocket

from api.schemas.agent_frames import AvailableSubnet

_registry: dict[UUID, AgentConnection] = {}
_lock = asyncio.Lock()


@dataclass
class AgentConnection:
    agent_id: UUID
    websocket: WebSocket
    connected_at: datetime
    last_seen_at: datetime
    agent_version: str | None = None
    available_subnets: list[AvailableSubnet] | None = None


async def register(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None:
    async with _lock:
        existing = _registry.get(agent_id)
        if existing is not None and existing.websocket is not websocket:
            # Best-effort: the replaced socket may already be dead (client
            # gone before its handler's finally/unregister ran), so a raise
            # here must not block installing the new connection below.
            try:
                await existing.websocket.close(code=4000, reason="replaced")
            except Exception:
                pass
        _registry[agent_id] = AgentConnection(
            agent_id=agent_id,
            websocket=websocket,
            connected_at=now,
            last_seen_at=now,
        )


async def unregister(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None:
    async with _lock:
        entry = _registry.get(agent_id)
        if entry is None or entry.websocket is not websocket:
            return
        del _registry[agent_id]


def is_online(agent_id: UUID) -> bool:
    return agent_id in _registry


def get_socket(agent_id: UUID) -> WebSocket | None:
    entry = _registry.get(agent_id)
    if entry is None:
        return None
    return entry.websocket


def last_seen_at(agent_id: UUID) -> datetime | None:
    entry = _registry.get(agent_id)
    if entry is None:
        return None
    return entry.last_seen_at


async def set_hello(
    agent_id: UUID,
    websocket: WebSocket,
    *,
    agent_version: str,
    available_subnets: list[AvailableSubnet],
    now: datetime,
) -> None:
    async with _lock:
        entry = _registry.get(agent_id)
        if entry is None or entry.websocket is not websocket:
            return
        entry.agent_version = agent_version
        entry.available_subnets = available_subnets
        entry.last_seen_at = now


async def touch(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None:
    async with _lock:
        entry = _registry.get(agent_id)
        if entry is None or entry.websocket is not websocket:
            return
        entry.last_seen_at = now


def get_hello(agent_id: UUID) -> tuple[str, list[AvailableSubnet]] | None:
    entry = _registry.get(agent_id)
    if entry is None or entry.agent_version is None or entry.available_subnets is None:
        return None
    return entry.agent_version, entry.available_subnets
