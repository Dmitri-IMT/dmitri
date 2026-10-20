from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
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


class AgentUpdateHelloContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: UUID
    invocation_id: UUID


class AgentHello(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hello"] = "hello"
    agent_version: str
    available_subnets: list[AvailableSubnet]
    capabilities: list[str] | None = None
    updater_version: str | None = None
    package_version: str | None = None
    os_suite: str | None = None
    architecture: str | None = None
    update_context: AgentUpdateHelloContext | None = None


class UpdateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["update_session"]
    session_id: UUID
    protocol_version: Literal[1]
    capabilities: list[Literal["scan_finalization_v1", "agent_update_v1"]]


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["agent_update"]
    update_id: UUID
    session_id: UUID
    release_id: UUID
    target_package_version: constr(min_length=1, max_length=128)
    sha256: constr(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime

    @model_validator(mode="after")
    def validate_deadline(self) -> AgentUpdate:
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return self


class ScanStatusAck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["scan_status_ack"]
    session_id: UUID
    command_id: UUID
    status: Literal["done", "failed", "cancelled", "expired"]
    has_results: bool


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


class AgentProgressSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal[
        "discovery",
        "ports",
        "deep_inspection",
        "ot_inspection",
        "targeted_assessment",
        "normalization",
        "uploading",
    ]
    percent: int = Field(ge=0, le=99)
    machines: int | None = Field(ge=0)
    open_ports: int | None = Field(ge=0)
    filtered_ports: int | None = Field(ge=0)
    industrial_services: int | None = Field(ge=0)
    vulnerabilities: int | None = Field(ge=0)


class AgentProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["progress"] = "progress"
    command_id: UUID
    scan_id: UUID
    sequence: int = Field(ge=1)
    progress: AgentProgressSnapshot


InboundCommandFrame = Annotated[
    AgentCommand | AgentCancel | AgentUpdate | UpdateSession | ScanStatusAck,
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
        protocol_probe: Callable[[], bool] | None = None,
        update_state_provider: (
            Callable[[], Awaitable[dict[str, Any] | None]] | None
        ) = None,
    ) -> None:
        self._device_id = str(config.device_id)
        self._private_key = config.private_key
        self._path = _COMMAND_PATH.format(device_id=self._device_id)
        self._url = _websocket_origin(config.backend_url) + self._path
        self._connect = connect
        self._sleep = sleep
        self._detect_subnets = detect_subnets
        self._agent_version = agent_version or installed_version()
        self._protocol_probe = protocol_probe
        self._protocol_supported = False
        self._protocol_negotiated = False
        self._probe_capabilities: set[str] = set()
        self._agent_update_ready = False
        self._update_state: dict[str, Any] = {}
        self._update_state_provider = update_state_provider
        self._session_id: UUID | None = None
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

    @property
    def supports_scan_finalization(self) -> bool:
        return "scan_finalization_v1" in self._probe_capabilities

    @property
    def supports_agent_updates(self) -> bool:
        return (
            "agent_update_v1" in self._probe_capabilities and self._agent_update_ready
        )

    def set_update_state_provider(
        self, provider: Callable[[], Awaitable[dict[str, Any] | None]]
    ) -> None:
        self._update_state_provider = provider

    @property
    def session_id(self) -> UUID | None:
        return self._session_id

    async def run(
        self,
        on_command: Callable[[AgentCommand], Awaitable[None]],
        on_connected: Callable[[], Awaitable[None]] | None = None,
        on_parked: Callable[[], Awaitable[None]] | None = None,
        *,
        on_cancel: Callable[[UUID], Awaitable[None]] | None = None,
        on_scan_status_ack: Callable[[ScanStatusAck], Awaitable[None]] | None = None,
        on_agent_update: Callable[[AgentUpdate], Awaitable[None]] | None = None,
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
                await self._serve_once(
                    on_command,
                    on_cancel,
                    on_connected,
                    on_scan_status_ack,
                    on_agent_update,
                )
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

    async def send_progress(self, progress: AgentProgress) -> bool:
        try:
            await self._send(progress)
        except _NotConnected:
            return False
        except _TRANSPORT_ERRORS as exc:
            LOGGER.warning("progress frame not delivered: %s", _describe(exc))
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
        on_scan_status_ack: Callable[[ScanStatusAck], Awaitable[None]] | None,
        on_agent_update: Callable[[AgentUpdate], Awaitable[None]] | None,
    ) -> None:
        await asyncio.to_thread(self._probe_protocol)
        self._protocol_negotiated = bool(self._probe_capabilities)
        self._session_id = None
        self._update_state = {}
        self._agent_update_ready = False
        if self._update_state_provider is not None:
            try:
                state = await self._update_state_provider()
            except (OSError, ValueError, TypeError):
                state = None
            if isinstance(state, dict):
                self._update_state = state
                self._agent_update_ready = bool(
                    "agent_update_v1" in self._probe_capabilities
                    and state.get("ready") is True
                    and state.get("supervisor_ready") is True
                    and type(state.get("updater_version")) is int
                    and state.get("updater_version") == 1
                    and state.get("scan_checkpoint_pending") is not True
                )
        self._socket = await self._connect(self._url, self._proof_headers())
        hello = self._hello()
        advertised_capabilities = set(hello.capabilities or [])
        await self._send(hello)
        self._ready = True
        LOGGER.info("command channel connected")
        if self._protocol_negotiated:
            raw_session = await self._socket.recv()
            frame = _parse_command(raw_session)
            if not isinstance(frame, UpdateSession) or not (
                advertised_capabilities.issubset(set(frame.capabilities))
            ):
                LOGGER.warning(
                    "invalid command session: raw_type=%s frame=%s capabilities=%s",
                    type(raw_session).__name__,
                    type(frame).__name__,
                    sorted(advertised_capabilities),
                )
                raise OSError("invalid finalization session")
            self._session_id = frame.session_id
        if on_connected is not None:
            await on_connected()
        if self._parked_reason is not None:
            return
        while True:
            frame = _parse_command(await self._socket.recv())
            if isinstance(frame, UpdateSession):
                # A socket cannot change its session after the initial handshake.
                if frame.session_id != self._session_id:
                    raise OSError("command session changed")
            elif isinstance(frame, ScanStatusAck):
                if on_scan_status_ack is not None:
                    await on_scan_status_ack(frame)
            elif isinstance(frame, AgentUpdate):
                if (
                    self.supports_agent_updates
                    and frame.session_id == self._session_id
                    and frame.expires_at > datetime.now(UTC)
                    and on_agent_update is not None
                ):
                    await on_agent_update(frame)
            elif isinstance(frame, AgentCancel):
                if on_cancel is not None:
                    await on_cancel(frame.command_id)
            elif frame is not None:
                await on_command(frame)

    def _proof_headers(self) -> dict[str, str]:
        return build_device_signature_headers(
            "GET", self._path, b"", self._device_id, self._private_key
        )

    def _hello(self) -> AgentHello:
        capabilities = []
        if self.supports_scan_finalization:
            capabilities.append("scan_finalization_v1")
        if self.supports_agent_updates:
            capabilities.append("agent_update_v1")
        update_fields = {}
        if (
            self._protocol_negotiated
            and self._update_state.get("supervisor_ready") is True
        ):
            runtime_version = self._update_state.get("updater_version")
            context = self._update_state.get("update_context")
            update_fields = {
                "updater_version": (
                    str(runtime_version) if type(runtime_version) is int else None
                ),
                "package_version": self._update_state.get("package_version"),
                "os_suite": self._update_state.get("os_suite"),
                "architecture": self._update_state.get("architecture"),
                "update_context": context,
            }
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
            capabilities=capabilities or None,
            **update_fields,
        )

    def _probe_protocol(self) -> bool:
        self._probe_capabilities = set()
        self._protocol_supported = False
        if self._protocol_probe is not None:
            result = self._protocol_probe()
            self._probe_capabilities = (
                set(result)
                if isinstance(result, (list, set, tuple))
                else ({"scan_finalization_v1"} if result else set())
            )
            self._protocol_supported = (
                "scan_finalization_v1" in self._probe_capabilities
            )
            return self._protocol_supported
        # Injected websocket connectors are test/local transports and must not
        # cause an unrelated network request.
        if self._connect is not _default_connect:
            return False
        path = f"/api/v1/agents/{self._device_id}/update-protocol"
        body = b""
        headers = build_device_signature_headers(
            "GET", path, body, self._device_id, self._private_key
        )
        try:
            response = httpx.get(
                self._url.replace("wss://", "https://")
                .replace("ws://", "http://")
                .split("/api/v1/agents/", 1)[0]
                + path,
                headers=headers,
                timeout=10.0,
                follow_redirects=False,
            )
        except httpx.TransportError as exc:
            raise OSError("protocol probe unavailable") from exc
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            raise OSError("protocol probe unavailable")
        try:
            payload = response.json()
            if (
                not isinstance(payload, dict)
                or set(payload) != {"protocol_versions", "capabilities"}
                or not isinstance(payload["protocol_versions"], list)
                or any(type(item) is not int for item in payload["protocol_versions"])
                or not isinstance(payload["capabilities"], list)
                or any(not isinstance(item, str) for item in payload["capabilities"])
            ):
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise OSError("invalid protocol probe response") from exc
        if 1 not in payload["protocol_versions"]:
            return False
        self._probe_capabilities = set(payload["capabilities"]) & {
            "scan_finalization_v1",
            "agent_update_v1",
        }
        self._protocol_supported = "scan_finalization_v1" in self._probe_capabilities
        return self._protocol_supported

    async def _send(self, frame: BaseModel) -> None:
        async with self._send_lock:
            socket = self._socket
            if socket is None:
                raise _NotConnected("command channel is not connected")
            await socket.send(
                frame.model_dump_json(exclude_none=isinstance(frame, AgentHello))
            )

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
