from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any
from uuid import UUID

import pytest
from agent.transport.command_channel import (
    AgentCommand,
    AgentStatus,
    CommandChannelClient,
)
from agent.transport.ingest import IngestConfig
from agent.utils.network import AvailableSubnetInfo
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.frames import Close
from websockets.http11 import Response

DEVICE_ID = UUID("6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d")
PRIVATE_KEY = bytes.fromhex("ab" * 32)
COMMAND_ID = UUID("11111111-2222-4333-8444-555555555555")
SCAN_ID = UUID("99999999-8888-4777-8666-555555555555")
COMMAND_PATH = f"/api/v1/agents/{DEVICE_ID}/commands"
SUBNETS = [AvailableSubnetInfo("eth0", "192.168.1.0/24", True)]
SUBNET_FRAMES = [
    {"interface": "eth0", "cidr": "192.168.1.0/24", "is_default_route": True}
]
PROOF_HEADERS = {
    "X-Device-Id",
    "X-Timestamp",
    "X-Nonce",
    "X-Body-SHA256",
    "X-Signature",
}


class Halt(Exception):
    pass


def make_config(backend_url: str = "https://api.example.com") -> IngestConfig:
    return IngestConfig(
        backend_url=backend_url, device_id=DEVICE_ID, private_key=PRIVATE_KEY
    )


def command_frame(**overrides: Any) -> str:
    frame = {
        "type": "command",
        "command_id": str(COMMAND_ID),
        "scan_id": str(SCAN_ID),
        "scan_mode": "quick",
        "subnet": "192.168.1.0/24",
    }
    frame.update(overrides)
    return json.dumps(frame)


def closed(code: int, reason: str) -> ConnectionClosed:
    return ConnectionClosed(Close(code, reason), None)


def rejected(status_code: int) -> InvalidStatus:
    return InvalidStatus(Response(status_code, "nope", Headers()))


class FakeSocket:
    def __init__(self, script: list[Any], log: list[Any]) -> None:
        self.sent: list[str] = []
        self.closed = False
        self._script = list(script)
        self._log = log

    async def send(self, frame: str) -> None:
        self._log.append(("send-start", frame))
        await asyncio.sleep(0)
        self.sent.append(frame)
        self._log.append(("send-end", frame))

    async def recv(self) -> str:
        self._log.append(("recv", None))
        await asyncio.sleep(0)
        if not self._script:
            raise closed(1006, "gone")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


class FailingSendSocket(FakeSocket):
    async def send(self, frame: str) -> None:
        raise OSError("write failed")


class Dialer:
    def __init__(self, *outcomes: Any, socket_class: type[FakeSocket] = FakeSocket):
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.sockets: list[FakeSocket] = []
        self.log: list[Any] = []
        self._outcomes = list(outcomes)
        self._socket_class = socket_class

    async def __call__(self, url: str, headers: dict[str, str]) -> Any:
        self.calls.append((url, dict(headers)))
        if not self._outcomes:
            raise Halt()
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        socket = self._socket_class(outcome, self.log)
        self.sockets.append(socket)
        return socket

    @property
    def headers(self) -> list[dict[str, str]]:
        return [headers for _, headers in self.calls]


class Sleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
        await asyncio.sleep(0)


def build_client(
    dialer: Dialer,
    sleeper: Sleeper | None = None,
    config: IngestConfig | None = None,
) -> CommandChannelClient:
    return CommandChannelClient(
        config or make_config(),
        connect=dialer,
        sleep=sleeper or Sleeper(),
        detect_subnets=lambda: list(SUBNETS),
        agent_version="9.9.9",
    )


async def drive(
    client: CommandChannelClient,
    on_connected: Any = None,
) -> list[AgentCommand]:
    commands: list[AgentCommand] = []

    async def record(command: AgentCommand) -> None:
        commands.append(command)

    with contextlib.suppress(Halt):
        await client.run(record, on_connected)
    return commands


class TestUpgradeTarget:
    def test_https_origin_becomes_wss_with_documented_path(self) -> None:
        client = build_client(Dialer())

        assert client.url == f"wss://api.example.com{COMMAND_PATH}"

    def test_http_origin_becomes_ws(self) -> None:
        client = build_client(Dialer(), config=make_config("http://10.0.0.5:8000/"))

        assert client.url == f"ws://10.0.0.5:8000{COMMAND_PATH}"

    @pytest.mark.asyncio
    async def test_dialed_path_uuid_matches_device_id_header(self) -> None:
        dialer = Dialer([])
        client = build_client(dialer)

        await drive(client)

        url, headers = dialer.calls[0]
        assert url == client.url
        assert url.rsplit("/", 2)[-2] == headers["X-Device-Id"]

    @pytest.mark.asyncio
    async def test_every_dial_carries_a_fresh_full_proof(self) -> None:
        dialer = Dialer([], [])
        client = build_client(dialer)

        await drive(client)

        assert len(dialer.headers) == 3
        for headers in dialer.headers:
            assert set(headers) == PROOF_HEADERS
        first, second = dialer.headers[0], dialer.headers[1]
        for name in ("X-Nonce", "X-Signature"):
            assert first[name] != second[name]


class TestHello:
    @pytest.mark.asyncio
    async def test_hello_precedes_on_connected_and_first_read(self) -> None:
        dialer = Dialer([command_frame()])
        client = build_client(dialer)
        order: list[str] = []

        async def on_connected() -> None:
            order.append("connected")

        await drive(client, on_connected)

        assert dialer.log[0][0] == "send-start"
        assert json.loads(dialer.log[0][1])["type"] == "hello"
        assert order == ["connected"]
        assert dialer.log.index(("recv", None)) > 1

    @pytest.mark.asyncio
    async def test_one_fresh_hello_per_upgrade_including_reconnect(self) -> None:
        dialer = Dialer([command_frame()], [])
        client = build_client(dialer)

        await drive(client)

        for socket in dialer.sockets:
            hellos = [
                json.loads(frame)
                for frame in socket.sent
                if json.loads(frame)["type"] == "hello"
            ]
            assert len(hellos) == 1
            assert hellos[0]["agent_version"] == "9.9.9"
            assert hellos[0]["available_subnets"] == SUBNET_FRAMES

    @pytest.mark.asyncio
    async def test_hello_reflects_subnets_enumerated_at_connect_time(self) -> None:
        dialer = Dialer([], [])
        enumerations = [
            [AvailableSubnetInfo("eth0", "10.0.0.0/24", True)],
            [AvailableSubnetInfo("wlan0", "10.1.0.0/24", False)],
        ]
        client = CommandChannelClient(
            make_config(),
            connect=dialer,
            sleep=Sleeper(),
            detect_subnets=lambda: enumerations.pop(0),
            agent_version="9.9.9",
        )

        await drive(client)

        cidrs = [
            json.loads(socket.sent[0])["available_subnets"][0]["cidr"]
            for socket in dialer.sockets
        ]
        assert cidrs == ["10.0.0.0/24", "10.1.0.0/24"]


class TestInboundValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "frame",
        [
            "{not json",
            json.dumps({"type": "error", "error_code": "boom"}),
            command_frame(type="status"),
            command_frame(priority="high"),
            command_frame(command_id="not-a-uuid"),
            command_frame(scan_mode="turbo"),
            command_frame(subnet="192.168.1.0/33"),
        ],
    )
    async def test_invalid_frame_is_not_dispatched_and_socket_stays_usable(
        self, frame: str
    ) -> None:
        dialer = Dialer([frame, command_frame()])
        client = build_client(dialer)

        commands = await drive(client)

        assert len(commands) == 1
        assert commands[0].command_id == COMMAND_ID

    @pytest.mark.asyncio
    async def test_valid_command_is_dispatched_with_parsed_fields(self) -> None:
        dialer = Dialer([command_frame(scan_mode="nspi")])
        client = build_client(dialer)

        commands = await drive(client)

        assert commands[0].scan_id == SCAN_ID
        assert commands[0].scan_mode == "nspi"
        assert commands[0].subnet == "192.168.1.0/24"


class TestSending:
    @pytest.mark.asyncio
    async def test_concurrent_sends_are_serialized(self) -> None:
        dialer = Dialer([])
        client = build_client(dialer)

        async def on_connected() -> None:
            await asyncio.gather(
                client.send_status(
                    AgentStatus(command_id=COMMAND_ID, status="running")
                ),
                client.send_status(
                    AgentStatus(command_id=COMMAND_ID, status="uploading")
                ),
            )

        await drive(client, on_connected)

        writes = [entry for entry in dialer.log if entry[0].startswith("send-")]
        assert [entry[0] for entry in writes] == [
            "send-start",
            "send-end",
        ] * 3
        assert all(
            writes[index][1] == writes[index + 1][1]
            for index in range(0, len(writes), 2)
        )

    @pytest.mark.asyncio
    async def test_send_status_reports_false_when_not_connected(self) -> None:
        client = build_client(Dialer())

        assert (
            await client.send_status(
                AgentStatus(command_id=COMMAND_ID, status="failed")
            )
            is False
        )


class TestBackoff:
    @pytest.mark.asyncio
    async def test_reconnect_is_visible_in_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        dialer = Dialer([closed(1006, "gone")], [])
        client = build_client(dialer)

        with caplog.at_level(logging.INFO):
            await drive(client)

        messages = [record.getMessage() for record in caplog.records]
        assert messages.count("command channel connected") == 2
        assert any("command channel lost:" in message for message in messages)

    @pytest.mark.asyncio
    async def test_pinned_schedule_and_cap(self) -> None:
        dialer = Dialer(*[OSError("down")] * 6)
        sleeper = Sleeper()
        client = build_client(dialer, sleeper)

        await drive(client)

        assert sleeper.delays == [1.0, 2.0, 5.0, 10.0, 30.0, 30.0]

    @pytest.mark.asyncio
    async def test_backoff_resets_after_upgrade_and_hello(self) -> None:
        dialer = Dialer(OSError("down"), OSError("down"), [])
        sleeper = Sleeper()
        client = build_client(dialer, sleeper)

        await drive(client)

        assert sleeper.delays == [1.0, 2.0, 1.0]

    @pytest.mark.asyncio
    async def test_backoff_does_not_reset_when_hello_send_fails(self) -> None:
        dialer = Dialer(OSError("down"), [], socket_class=FailingSendSocket)
        sleeper = Sleeper()
        client = build_client(dialer, sleeper)

        await drive(client)

        assert sleeper.delays == [1.0, 2.0]


class TestClassification:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "outcome",
        [
            rejected(403),
            closed(4000, "replaced"),
            closed(4001, "device revoked"),
        ],
    )
    async def test_permanent_failures_park_without_redialing(
        self, outcome: BaseException
    ) -> None:
        dialer = Dialer(outcome)
        sleeper = Sleeper()
        client = build_client(dialer, sleeper)

        await drive(client)

        assert client.parked_reason is not None
        assert len(dialer.calls) == 1
        assert sleeper.delays == []

    @pytest.mark.asyncio
    async def test_permanent_close_mid_session_parks(self) -> None:
        dialer = Dialer([closed(4000, "replaced")])
        client = build_client(dialer)

        await drive(client)

        assert client.parked_reason is not None
        assert len(dialer.calls) == 1
        assert dialer.sockets[0].closed is True

    @pytest.mark.asyncio
    async def test_unauthorized_retries_with_a_completely_fresh_proof(self) -> None:
        dialer = Dialer(rejected(401), [])
        client = build_client(dialer)

        await drive(client)

        assert client.parked_reason is None
        assert len(dialer.calls) >= 2
        first, second = dialer.headers[0], dialer.headers[1]
        for name in ("X-Nonce", "X-Signature"):
            assert first[name] != second[name]

    @pytest.mark.asyncio
    async def test_close_parks_and_stops_the_loop(self) -> None:
        dialer = Dialer([])
        client = build_client(dialer)
        await client.close("shutting down")

        await drive(client)

        assert client.parked_reason == "shutting down"
        assert dialer.calls == []


class TestSecretSafety:
    @pytest.mark.asyncio
    async def test_diagnostics_never_leak_key_signature_or_signed_url(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        dialer = Dialer(OSError("down"), ["{not json"], rejected(403))
        client = build_client(dialer)

        with caplog.at_level(logging.DEBUG):
            await drive(client)

        emitted = caplog.text + str(client.parked_reason)
        assert PRIVATE_KEY.hex() not in emitted
        for headers in dialer.headers:
            assert headers["X-Signature"] not in emitted
            assert headers["X-Nonce"] not in emitted
        assert "X-Signature" not in emitted
