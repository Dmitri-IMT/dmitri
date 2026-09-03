from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
from collections.abc import Awaitable, Callable
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    ValidationError,
    constr,
    model_validator,
)
from websockets.asyncio.client import connect as websocket_connect
from websockets.exceptions import ConnectionClosed, InvalidStatus, WebSocketException

from agent.normalize.contracts import SubnetCIDR
from agent.transport.ingest import IngestConfig
from agent.transport.signing import build_device_signature_headers
from agent.utils.network import AvailableSubnetInfo, detect_available_subnets

LOGGER = logging.getLogger(__name__)

_COMMAND_PATH = "/api/v1/agents/{device_id}/commands"
_BACKOFF_SCHEDULE = (1.0, 2.0, 5.0, 10.0, 30.0)
_PERMANENT_CLOSE_FLOOR = 4000
_TRANSPORT_ERRORS = (OSError, WebSocketException)


class _NotConnected(RuntimeError):
    pass


def _ipv4_network(value: str) -> str:
    ipaddress.IPv4Network(value, strict=False)
    return value


CIDR = Annotated[SubnetCIDR, AfterValidator(_ipv4_network)]


class AvailableSubnet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface: constr(min_length=1)
    cidr: CIDR
    is_default_route: bool


class AgentHello(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hello"] = "hello"
    agent_version: str
    available_subnets: list[AvailableSubnet]


class NspiOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    submode: Literal["inventory", "read_only_mapping", "active_validation"] = (
        "inventory"
    )
    active_risk_acknowledged: bool = False
    change_ticket: constr(min_length=1, max_length=120) | None = None

    @model_validator(mode="after")
    def validate_active_confirmation(self) -> NspiOptions:
        if self.submode == "active_validation":
            if not self.active_risk_acknowledged or self.change_ticket is None:
                raise ValueError(
                    "active_validation requires acknowledgement and change_ticket"
                )
        elif self.active_risk_acknowledged or self.change_ticket is not None:
            raise ValueError(
                "active acknowledgement and change_ticket require active_validation"
            )
        return self


class AgentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["command"]
    command_id: UUID
    scan_id: UUID
    scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"]
    subnet: CIDR
    nspi_options: NspiOptions | None = None

    @model_validator(mode="after")
    def validate_nspi_options(self) -> AgentCommand:
        if self.scan_mode != "nspi" and self.nspi_options is not None:
            raise ValueError("nspi_options requires scan_mode='nspi'")
        return self


class AgentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["status"] = "status"
    command_id: UUID
    status: Literal["running", "uploading", "done", "failed"]
    error_code: str | None = None


def _installed_version() -> str:
    try:
        return version("hardware-agent")
    except PackageNotFoundError:
        return "unknown"


def _websocket_origin(backend_url: str) -> str:
    scheme, _, rest = backend_url.partition("://")
    return ("wss://" if scheme == "https" else "ws://") + rest.rstrip("/")


async def _default_connect(url: str, headers: dict[str, str]) -> Any:
    return await websocket_connect(url, additional_headers=headers)


def _permanent_reason(exc: BaseException) -> str | None:
    if isinstance(exc, InvalidStatus) and exc.response.status_code == 403:
        return "backend refused the device (403); not reconnecting"
    if isinstance(exc, ConnectionClosed):
        if exc.code == _PERMANENT_CLOSE_FLOOR and exc.reason == "replaced":
            return "another daemon owns this device slot; not reconnecting"
        if exc.code >= _PERMANENT_CLOSE_FLOOR:
            return f"backend closed the channel permanently ({exc.code})"
    return None


def _describe(exc: BaseException) -> str:
    if isinstance(exc, InvalidStatus):
        return f"upgrade rejected with status {exc.response.status_code}"
    if isinstance(exc, ConnectionClosed):
        return f"connection closed with code {exc.code}"
    return type(exc).__name__


class CommandChannelClient:
    def __init__(
        self,
        config: IngestConfig,
        *,
        connect: Callable[[str, dict[str, str]], Awaitable[Any]] = _default_connect,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        detect_subnets: Callable[
            [], list[AvailableSubnetInfo]
        ] = detect_available_subnets,
        agent_version: str | None = None,
    ) -> None:
        self._device_id = str(config.device_id)
        self._private_key = config.private_key
        self._path = _COMMAND_PATH.format(device_id=self._device_id)
        self._url = _websocket_origin(config.backend_url) + self._path
        self._connect = connect
        self._sleep = sleep
        self._detect_subnets = detect_subnets
        self._agent_version = agent_version or _installed_version()
        self._send_lock = asyncio.Lock()
        self._socket: Any = None
        self._parked_reason: str | None = None
        self._ready = False

    @property
    def url(self) -> str:
        return self._url

    @property
    def parked_reason(self) -> str | None:
        return self._parked_reason

    async def run(
        self,
        on_command: Callable[[AgentCommand], Awaitable[None]],
        on_connected: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        attempt = 0
        while self._parked_reason is None:
            self._ready = False
            try:
                await self._serve_once(on_command, on_connected)
            except _TRANSPORT_ERRORS as exc:
                reason = _permanent_reason(exc)
                if reason is not None:
                    self._park(reason)
                else:
                    LOGGER.warning("command channel lost: %s", _describe(exc))
            finally:
                await self._drop_socket()
            if self._parked_reason is not None:
                return
            if self._ready:
                attempt = 0
            index = min(attempt, len(_BACKOFF_SCHEDULE) - 1)
            await self._sleep(_BACKOFF_SCHEDULE[index])
            attempt += 1

    async def send_status(self, status: AgentStatus) -> bool:
        try:
            await self._send(status)
        except _NotConnected:
            return False
        except _TRANSPORT_ERRORS as exc:
            LOGGER.warning("status frame not delivered: %s", _describe(exc))
            return False
        return True

    async def close(self, reason: str = "command channel closed") -> None:
        self._park(reason)
        await self._drop_socket()

    async def _serve_once(
        self,
        on_command: Callable[[AgentCommand], Awaitable[None]],
        on_connected: Callable[[], Awaitable[None]] | None,
    ) -> None:
        self._socket = await self._connect(self._url, self._proof_headers())
        await self._send(self._hello())
        self._ready = True
        LOGGER.info("command channel connected")
        if on_connected is not None:
            await on_connected()
        while True:
            command = _parse_command(await self._socket.recv())
            if command is not None:
                await on_command(command)

    def _proof_headers(self) -> dict[str, str]:
        return build_device_signature_headers(
            "GET", self._path, b"", self._device_id, self._private_key
        )

    def _hello(self) -> AgentHello:
        return AgentHello(
            agent_version=self._agent_version,
            available_subnets=[
                AvailableSubnet(
                    interface=found.interface,
                    cidr=found.cidr,
                    is_default_route=found.is_default_route,
                )
                for found in self._detect_subnets()
            ],
        )

    async def _send(self, frame: BaseModel) -> None:
        async with self._send_lock:
            socket = self._socket
            if socket is None:
                raise _NotConnected("command channel is not connected")
            await socket.send(frame.model_dump_json())

    async def _drop_socket(self) -> None:
        socket, self._socket = self._socket, None
        if socket is not None:
            with contextlib.suppress(*_TRANSPORT_ERRORS):
                await socket.close()

    def _park(self, reason: str) -> None:
        if self._parked_reason is None:
            self._parked_reason = reason
            LOGGER.error("command channel parked: %s", reason)


def _parse_command(raw: object) -> AgentCommand | None:
    try:
        return AgentCommand.model_validate_json(raw)
    except (ValidationError, ValueError, TypeError):
        LOGGER.warning("discarding an invalid inbound frame")
        return None
