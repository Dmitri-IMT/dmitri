from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.services import agent_connections, device_sig
from conftest import ws_upgrade_headers

EMPTY_BODY_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)


def _verify_get_envelope(public_key: bytes, headers: dict[str, str], path: str) -> None:
    canonical = device_sig.canonical_string(
        "GET",
        path,
        headers["X-Device-Id"],
        headers["X-Timestamp"],
        headers["X-Nonce"],
        headers["X-Body-SHA256"],
    )
    device_sig.verify(public_key, canonical, headers["X-Signature"])


def test_ws_upgrade_headers_defaults_resolved_path_and_empty_body():
    private_key, public_key = device_sig.generate_keypair()
    agent_id = uuid4()
    headers = ws_upgrade_headers(private_key, agent_id)
    resolved_path = f"/api/v1/agents/{agent_id}/commands"

    assert headers["X-Body-SHA256"] == EMPTY_BODY_SHA256
    assert headers["X-Device-Id"] == str(agent_id)
    _verify_get_envelope(public_key, headers, resolved_path)


def test_ws_upgrade_headers_custom_path_is_signed():
    private_key, public_key = device_sig.generate_keypair()
    agent_id = uuid4()
    custom_path = "/other/ws/path"
    headers = ws_upgrade_headers(private_key, agent_id, path=custom_path)
    _verify_get_envelope(public_key, headers, custom_path)


def test_ws_upgrade_headers_does_not_sign_route_template():
    private_key, public_key = device_sig.generate_keypair()
    agent_id = uuid4()
    headers = ws_upgrade_headers(private_key, agent_id)
    template_path = "/api/v1/agents/{agent_id}/commands"
    canonical = device_sig.canonical_string(
        "GET",
        template_path,
        headers["X-Device-Id"],
        headers["X-Timestamp"],
        headers["X-Nonce"],
        headers["X-Body-SHA256"],
    )
    with pytest.raises(device_sig.SignatureError):
        device_sig.verify(public_key, canonical, headers["X-Signature"])


def test_agent_connections_registry_empty_at_test_start():
    # Relies on the autouse `clear_agent_connections_registry` fixture in
    # conftest.py, which resets the registry before/after every test — that
    # is what keeps this assertion true regardless of test ordering.
    assert not agent_connections._registry


def test_agent_connections_registry_mutation_does_not_leak():
    ws = AsyncMock()
    asyncio.run(agent_connections.register(uuid4(), ws, now=datetime.now(UTC)))
    assert agent_connections._registry
