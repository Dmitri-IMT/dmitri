from __future__ import annotations

import json
import stat
from uuid import uuid4

import httpx
import pytest
from agent.transport.provision import (
    ProvisionError,
    is_provisioned,
    load_or_create_key,
    parse_https_url,
    provision,
    register,
)


def test_plain_http_is_refused() -> None:
    with pytest.raises(ProvisionError, match="https://"):
        parse_https_url("http://backend.example")


def test_the_key_is_created_once_and_kept_private(tmp_path) -> None:
    env_file = tmp_path / "agent.env"

    first = load_or_create_key(env_file)

    assert load_or_create_key(env_file) == first
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert not is_provisioned(env_file)


def test_register_logs_in_then_sends_the_public_key() -> None:
    agent_id = uuid4()
    seen: list[tuple[str, dict, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.url.path,
                json.loads(request.content),
                request.headers.get("Authorization"),
            )
        )
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(201, json={"agent_id": str(agent_id)})

    client = httpx.Client(
        base_url="https://backend.example", transport=httpx.MockTransport(handler)
    )

    result = register(
        client,
        email="admin@example.com",
        password="pw",
        display_name="Lab Pi",
        public_key="ab" * 32,
    )

    assert result == agent_id
    assert seen == [
        ("/api/v1/auth/login", {"email": "admin@example.com", "password": "pw"}, None),
        (
            "/api/v1/agents",
            {"display_name": "Lab Pi", "public_key": "ab" * 32},
            "Bearer tok",
        ),
    ]


def test_a_failed_login_keeps_the_key_for_the_next_run(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "agent.env"
    answers = iter(["https://backend.example", "admin@example.com", "Lab Pi"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "wrong")
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(
            **kwargs, transport=httpx.MockTransport(lambda _r: httpx.Response(401))
        ),
    )

    with pytest.raises(ProvisionError, match="login failed: HTTP 401"):
        provision(env_file)

    assert not is_provisioned(env_file)
    assert "DEVICE_PRIVATE_KEY=" in env_file.read_text()
