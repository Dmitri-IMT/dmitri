from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
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
from agent.version import installed_version

LOGGER = logging.getLogger(__name__)

_COMMAND_PATH = "/api/v1/agents/{device_id}/commands"
_BACKOFF_SCHEDULE = (1.0, 2.0, 5.0, 10.0, 30.0)
_PARK_RETRY_SECONDS = 3600.0
_PERMANENT_CLOSE_FLOOR = 4000
_TRANSPORT_ERRORS = (OSError, WebSocketException)

ParkReason = Literal["revoked", "replaced", "refused", "upload_refused"]


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


class AgentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["cancel"]
    command_id: UUID


class AgentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["status"] = "status"
    command_id: UUID
    status: Literal["running", "uploading", "done", "failed", "cancelled"]
    error_code: str | None = None


InboundCommandFrame = Annotated[
    AgentCommand | AgentCancel,
    Field(discriminator="type"),
]
_INBOUND_COMMAND_FRAME_ADAPTER = TypeAdapter(InboundCommandFrame)


def _websocket_origin(backend_url: str) -> str:
    scheme, _, rest = backend_url.partition("://")
    return ("wss://" if scheme == "https" else "ws://") + rest.rstrip("/")


async def _default_connect(url: str, headers: dict[str, str]) -> Any:
    return await websocket_connect(url, additional_headers=headers)


def _park_reason(exc: BaseException) -> ParkReason | None:
    if isinstance(exc, InvalidStatus) and exc.response.status_code == 403:
        return "refused"
    if isinstance(exc, ConnectionClosed):
        if exc.code == _PERMANENT_CLOSE_FLOOR and exc.reason == "replaced":
            return "replaced"
        if exc.code == 4001:
            return "revoked"
        if exc.code >= _PERMANENT_CLOSE_FLOOR:
            return "refused"
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
        self._agent_version = agent_version or installed_version()
        self._send_lock = asyncio.Lock()
        self._socket: Any = None
        self._parked_reason: ParkReason | None = None
        self._closed = False
        self._shutdown = asyncio.Event()
        self._ready = False

    @property
    def url(self) -> str:
        return self._url

    @property
    def parked_reason(self) -> ParkReason | None:
        return self._parked_reason

    async def run(
        self,
        on_command: Callable[[AgentCommand], Awaitable[None]],
        on_connected: Callable[[], Awaitable[None]] | None = None,
        on_parked: Callable[[], Awaitable[None]] | None = None,
        *,
        on_cancel: Callable[[UUID], Awaitable[None]] | None = None,
    ) -> None:
        attempt = 0
        while not self._closed:
            if self._parked_reason is not None:
                if on_parked is not None:
                    await on_parked()
                await self._wait_out_park()
                attempt = 0
                continue
            self._ready = False
            try:
                await self._serve_once(on_command, on_cancel, on_connected)
            except _TRANSPORT_ERRORS as exc:
                if reason := _park_reason(exc):
                    self._set_parked(reason)
                elif self._parked_reason is None:
                    LOGGER.warning("command channel lost: %s", _describe(exc))
            finally:
                await self._drop_socket()
            if self._closed or self._parked_reason is not None:
                continue
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

    async def park(self, reason: ParkReason) -> None:
        self._set_parked(reason)
        await self._drop_socket()

    async def close(self) -> None:
        self._closed = True
        self._shutdown.set()
        await self._drop_socket()

    async def _serve_once(
        self,
        on_command: Callable[[AgentCommand], Awaitable[None]],
        on_cancel: Callable[[UUID], Awaitable[None]] | None,
        on_connected: Callable[[], Awaitable[None]] | None,
    ) -> None:
        self._socket = await self._connect(self._url, self._proof_headers())
        await self._send(self._hello())
        self._ready = True
        LOGGER.info("command channel connected")
        if on_connected is not None:
            await on_connected()
        if self._parked_reason is not None:
            return
        while True:
            frame = _parse_command(await self._socket.recv())
            if isinstance(frame, AgentCancel):
                if on_cancel is not None:
                    await on_cancel(frame.command_id)
            elif frame is not None:
                await on_command(frame)

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

    def _set_parked(self, reason: ParkReason) -> None:
        if self._parked_reason is None:
            self._parked_reason = reason

    async def _wait_out_park(self) -> None:
        reason = self._parked_reason
        if reason is None or self._closed:
            return
        next_attempt = datetime.now(UTC) + timedelta(seconds=_PARK_RETRY_SECONDS)
        LOGGER.error(
            "command channel parked (%s); next attempt at %s",
            reason,
            next_attempt.isoformat(timespec="seconds"),
        )
        sleep_task = asyncio.create_task(self._sleep(_PARK_RETRY_SECONDS))
        shutdown_task = asyncio.create_task(self._shutdown.wait())
        shutdown_won = False
        try:
            done, _pending = await asyncio.wait(
                {sleep_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
            )
            shutdown_won = shutdown_task in done
        finally:
            for task in (sleep_task, shutdown_task):
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if shutdown_won or self._closed:
            return
        if sleep_task.cancelled():
            raise asyncio.CancelledError()
        exc = sleep_task.exception()
        if exc is not None:
            raise exc
        self._parked_reason = None


def _parse_command(raw: object) -> InboundCommandFrame | None:
    try:
        return _INBOUND_COMMAND_FRAME_ADAPTER.validate_json(raw)
    except (ValidationError, ValueError, TypeError):
        LOGGER.warning("discarding an invalid inbound frame")
        return None
