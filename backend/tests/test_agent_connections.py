from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from api.schemas.agent_frames import AvailableSubnet
from api.services import agent_connections

AGENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 27, 12, 1, 0, tzinfo=UTC)
T2 = datetime(2026, 7, 27, 12, 2, 0, tzinfo=UTC)
T3 = datetime(2026, 7, 27, 12, 3, 0, tzinfo=UTC)
SUBNETS = [
    AvailableSubnet(interface="eth0", cidr="10.0.0.0/24", is_default_route=False),
    AvailableSubnet(interface="wlan0", cidr="192.168.1.0/24", is_default_route=True),
]


@pytest.fixture(autouse=True)
def clear_registry():
    agent_connections._registry.clear()
    yield
    agent_connections._registry.clear()


def test_register_makes_agent_online():
    ws = AsyncMock()

    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    assert agent_connections.is_online(AGENT_ID)
    assert agent_connections.get_socket(AGENT_ID) is ws
    assert agent_connections.last_seen_at(AGENT_ID) == T0


def test_unregister_makes_agent_offline():
    ws = AsyncMock()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(agent_connections.unregister(AGENT_ID, ws, now=T1))

    assert not agent_connections.is_online(AGENT_ID)
    assert agent_connections.get_socket(AGENT_ID) is None
    assert agent_connections.last_seen_at(AGENT_ID) is None


def test_replace_closes_old_socket():
    ws_a = AsyncMock()
    ws_b = AsyncMock()

    asyncio.run(agent_connections.register(AGENT_ID, ws_a, now=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws_b, now=T1))

    ws_a.close.assert_awaited_once_with(code=4000, reason="replaced")
    assert agent_connections.is_online(AGENT_ID)
    assert agent_connections.get_socket(AGENT_ID) is ws_b


def test_stale_unregister_after_replace_leaves_new_socket_online():
    ws_a = AsyncMock()
    ws_b = AsyncMock()

    asyncio.run(agent_connections.register(AGENT_ID, ws_a, now=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws_b, now=T1))
    asyncio.run(agent_connections.unregister(AGENT_ID, ws_a, now=T2))

    assert agent_connections.is_online(AGENT_ID)
    assert agent_connections.get_socket(AGENT_ID) is ws_b
    assert agent_connections.last_seen_at(AGENT_ID) == T1


def test_reregister_same_socket_does_not_close():
    ws = AsyncMock()

    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T1))

    ws.close.assert_not_awaited()
    assert agent_connections.is_online(AGENT_ID)
    assert agent_connections.get_socket(AGENT_ID) is ws
    assert agent_connections.last_seen_at(AGENT_ID) == T1


def test_get_hello_before_and_after_set_hello():
    ws = AsyncMock()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    assert agent_connections.get_hello(AGENT_ID) is None

    asyncio.run(
        agent_connections.set_hello(
            AGENT_ID,
            ws,
            agent_version="1.0.0",
            available_subnets=SUBNETS,
            now=T1,
        )
    )

    assert agent_connections.get_hello(AGENT_ID) == ("1.0.0", SUBNETS)
    assert [s.is_default_route for s in agent_connections.get_hello(AGENT_ID)[1]] == [
        False,
        True,
    ]
    assert agent_connections.last_seen_at(AGENT_ID) == T1


def test_set_hello_and_touch_are_identity_aware():
    ws_a = AsyncMock()
    ws_b = AsyncMock()

    asyncio.run(agent_connections.register(AGENT_ID, ws_a, now=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws_b, now=T1))

    asyncio.run(
        agent_connections.set_hello(
            AGENT_ID,
            ws_a,
            agent_version="stale",
            available_subnets=SUBNETS,
            now=T2,
        )
    )
    asyncio.run(agent_connections.touch(AGENT_ID, ws_a, now=T3))

    assert agent_connections.get_hello(AGENT_ID) is None
    assert agent_connections.last_seen_at(AGENT_ID) == T1


def test_touch_bumps_last_seen_at():
    ws = AsyncMock()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(agent_connections.touch(AGENT_ID, ws, now=T1))

    assert agent_connections.last_seen_at(AGENT_ID) == T1


def test_unregister_does_not_bump_last_seen_at():
    ws = AsyncMock()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(agent_connections.unregister(AGENT_ID, ws, now=T3))

    assert agent_connections.last_seen_at(AGENT_ID) is None


def test_replace_swaps_registry_even_if_old_socket_close_raises():
    ws_a = AsyncMock()
    ws_b = AsyncMock()
    ws_a.close.side_effect = RuntimeError("already closed")

    asyncio.run(agent_connections.register(AGENT_ID, ws_a, now=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws_b, now=T1))

    assert agent_connections.get_socket(AGENT_ID) is ws_b
    assert len(agent_connections._registry) == 1


# Note: the tests above call asyncio.run(...) once per operation, so each
# mutation runs in its own event loop and never contends on _lock. The
# lock-contention path is exercised only by test_concurrent_register_leaves_one_entry
# below, which awaits both registers within a single event loop.
def test_concurrent_register_leaves_one_entry():
    agent_id = uuid4()
    ws_a = AsyncMock()
    ws_b = AsyncMock()

    async def run():
        await asyncio.gather(
            agent_connections.register(agent_id, ws_a, now=T0),
            agent_connections.register(agent_id, ws_b, now=T1),
        )

    asyncio.run(run())

    assert len(agent_connections._registry) == 1
    assert agent_connections.is_online(agent_id)
    assert agent_connections.get_socket(agent_id) in (ws_a, ws_b)
