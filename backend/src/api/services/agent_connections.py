from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator
from uuid import UUID, uuid4

from starlette.websockets import WebSocket, WebSocketState

from api.schemas.agent_frames import AvailableSubnet

CLOSE_REPLACED = 4000
CLOSE_REVOKED = 4001

_registry: dict[UUID, AgentConnection] = {}
_device_locks: dict[UUID, asyncio.Lock] = {}


def _device_lock(agent_id: UUID) -> asyncio.Lock:
    return _device_locks.setdefault(agent_id, asyncio.Lock())


@asynccontextmanager
async def device_guard(agent_id: UUID) -> AsyncIterator[None]:
    async with _device_lock(agent_id):
        yield


@dataclass
class AgentConnection:
    agent_id: UUID
    websocket: WebSocket
    connected_at: datetime
    last_seen_at: datetime
    session_id: UUID
    agent_version: str | None = None
    package_version: str | None = None
    available_subnets: list[AvailableSubnet] | None = None
    capabilities: frozenset[str] = frozenset()


async def register(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None:
    async with device_guard(agent_id):
        await register_locked(agent_id, websocket, now=now)


async def register_locked(
    agent_id: UUID, websocket: WebSocket, *, now: datetime
) -> None:
    existing = _registry.get(agent_id)
    if existing is not None and existing.websocket is not websocket:
        try:
            await existing.websocket.close(code=CLOSE_REPLACED, reason="replaced")
        except Exception:
            pass
    _registry[agent_id] = AgentConnection(
        agent_id=agent_id,
        websocket=websocket,
        connected_at=now,
        last_seen_at=now,
        session_id=uuid4(),
    )


async def close_revoked(websocket: WebSocket) -> None:
    if websocket.application_state is not WebSocketState.CONNECTED:
        return
    try:
        await websocket.close(code=CLOSE_REVOKED, reason="revoked")
    except Exception:
        pass


async def unregister(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None:
    async with device_guard(agent_id):
        unregister_locked(agent_id, websocket)


def unregister_locked(agent_id: UUID, websocket: WebSocket) -> bool:
    entry = _registry.get(agent_id)
    if entry is None or entry.websocket is not websocket:
        return False
    del _registry[agent_id]
    return True


def get_connection(agent_id: UUID) -> AgentConnection | None:
    return _registry.get(agent_id)


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
    package_version: str | None = None,
    capabilities: frozenset[str] = frozenset(),
    now: datetime,
) -> None:
    async with device_guard(agent_id):
        set_hello_locked(
            agent_id,
            websocket,
            agent_version=agent_version,
            available_subnets=available_subnets,
            package_version=package_version,
            capabilities=capabilities,
            now=now,
        )


def set_hello_locked(
    agent_id: UUID,
    websocket: WebSocket,
    *,
    agent_version: str,
    available_subnets: list[AvailableSubnet],
    package_version: str | None,
    capabilities: frozenset[str],
    now: datetime,
) -> bool:
    entry = _registry.get(agent_id)
    if entry is None or entry.websocket is not websocket:
        return False
    entry.agent_version = agent_version
    entry.package_version = package_version
    entry.capabilities = capabilities
    entry.available_subnets = available_subnets
    entry.last_seen_at = now
    return True


async def touch(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None:
    async with device_guard(agent_id):
        touch_locked(agent_id, websocket, now=now)


def touch_locked(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> bool:
    entry = _registry.get(agent_id)
    if entry is None or entry.websocket is not websocket:
        return False
    entry.last_seen_at = now
    return True


def get_hello(agent_id: UUID) -> tuple[str, list[AvailableSubnet]] | None:
    entry = _registry.get(agent_id)
    if entry is None or entry.agent_version is None or entry.available_subnets is None:
        return None
    return entry.agent_version, entry.available_subnets
