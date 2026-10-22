from __future__ import annotations

import asyncio
import ipaddress
import struct
import time
from dataclasses import dataclass
from typing import Any

from asyncua import ua
from asyncua.client.ua_client import UASocketProtocol
from asyncua.common.connection import TransportLimits
from asyncua.ua.ua_binary import uatcp_to_binary

MAX_FRAME = 65536
MAX_MESSAGE = 131072
MAX_CHUNKS = 16
MAX_TOTAL = 4 * 1024 * 1024
ALLOWED = {
    "OpenSecureChannelRequest",
    "GetEndpointsRequest",
    "CreateSessionRequest",
    "ActivateSessionRequest",
    "BrowseRequest",
    "BrowseNextRequest",
    "ReadRequest",
    "CloseSessionRequest",
    "CloseSecureChannelRequest",
}
ALLOWED_TYPES = {name: getattr(ua, name) for name in ALLOWED}
EXPECTED_MESSAGE_TYPES = {
    "OpenSecureChannelRequest": ua.MessageType.SecureOpen,
    "CloseSecureChannelRequest": ua.MessageType.SecureClose,
}


class ProtocolViolation(Exception):
    pass


@dataclass(slots=True)
class SendStats:
    requests: int = 0
    attempts: int = 0
    blocked: int = 0
    by_service: dict[str, int] | None = None
    bytes_sent: int = 0
    bytes_received: int = 0
    chunks_sent: int = 0
    chunks_received: int = 0
    request_count_known: bool = True


class RequestGate:
    def __init__(self, budget: int, pacing: float = 0.1) -> None:
        if budget < 0 or budget > 32 or pacing < 0.1:
            raise ValueError("invalid_limits")
        self.budget = budget
        self.ordinary_limit = max(0, budget - 2)
        self.pacing = pacing
        self.stats = SendStats()
        self.stats.by_service = {}
        self.last_send = 0.0
        self._cleanup = {
            "CloseSessionRequest": False,
            "CloseSecureChannelRequest": False,
        }
        self._permit: tuple[type, int] | None = None
        self._serial = 0
        self.pending_service: str | None = None
        self.armed_service: str | None = None

    def authorize(self, request: Any, type_id: Any) -> int:
        cls = type(request)
        name = cls.__name__
        oid = getattr(ua.ObjectIds, f"{name}_Encoding_DefaultBinary", None)
        if (
            ALLOWED_TYPES.get(name) is not cls
            or oid is None
            or type_id != ua.NodeId(oid)
        ):
            self.stats.attempts += 1
            self.stats.blocked += 1
            raise ProtocolViolation("service_not_allowed")
        if self._permit is not None or self.armed_service is not None:
            self.stats.attempts += 1
            self.stats.blocked += 1
            raise ProtocolViolation("service_not_allowed")
        if name in self._cleanup:
            if self._cleanup[name]:
                self.stats.attempts += 1
                self.stats.blocked += 1
                raise ProtocolViolation("service_not_allowed")
            self._cleanup[name] = True
        elif self.stats.requests >= self.ordinary_limit:
            self.stats.attempts += 1
            self.stats.blocked += 1
            raise ProtocolViolation("request_budget_exhausted")
        self._serial += 1
        self.pending_service = name.removesuffix("Request")
        self._permit = (cls, self._serial)
        return self._serial

    def take(self, request: Any, permit: int) -> None:
        if self._permit != (type(request), permit):
            self.stats.attempts += 1
            self.stats.blocked += 1
            self._permit = None
            raise ProtocolViolation("service_not_allowed")
        self._permit = None
        self.armed_service = self.pending_service

    def disarm(self) -> None:
        self._permit = None
        self.armed_service = None
        self.pending_service = None

    def release_before_send(self, service: str) -> None:
        name = f"{service}Request"
        if name in self._cleanup:
            self._cleanup[name] = False

    async def wait_admission(self, cancelled: asyncio.Event, deadline: float) -> None:
        delay = max(0.0, self.pacing - (time.monotonic() - self.last_send) + 0.02)
        if time.monotonic() + delay >= deadline:
            raise TimeoutError("deadline")
        if delay:
            try:
                await asyncio.wait_for(cancelled.wait(), delay)
                raise asyncio.CancelledError
            except asyncio.TimeoutError:
                pass
        if cancelled.is_set() or time.monotonic() >= deadline:
            raise asyncio.CancelledError


class BoundedFramer:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.message_size = 0
        self.message_chunks = 0
        self.total = 0
        self.message_type: bytes | None = None

    def feed(self, data: bytes) -> list[bytes]:
        if len(self.buffer) + len(data) > MAX_MESSAGE:
            raise ProtocolViolation("message_size_limit")
        self.buffer.extend(data)
        self.total += len(data)
        if self.total > MAX_TOTAL:
            raise ProtocolViolation("message_size_limit")
        frames: list[bytes] = []
        while len(self.buffer) >= 8:
            message_type, chunk_type, size = struct.unpack("<3sBI", self.buffer[:8])
            if (
                message_type not in {b"HEL", b"ACK", b"ERR", b"OPN", b"MSG", b"CLO"}
                or chunk_type not in (ord("F"), ord("C"), ord("A"))
                or size < 8
                or size > MAX_FRAME
            ):
                raise ProtocolViolation("message_size_limit")
            if message_type in {b"HEL", b"ACK", b"ERR", b"CLO"} and chunk_type != ord(
                "F"
            ):
                raise ProtocolViolation("message_size_limit")
            if chunk_type == ord("A") and (
                message_type not in {b"OPN", b"MSG"} or self.message_chunks == 0
            ):
                raise ProtocolViolation("message_size_limit")
            if message_type == b"HEL" and size < 32:
                raise ProtocolViolation("message_size_limit")
            if len(self.buffer) < size:
                break
            if message_type == b"ACK":
                if size != 28 or chunk_type != ord("F"):
                    raise ProtocolViolation("message_size_limit")
                ack = struct.unpack("<5I", self.buffer[8:28])
                if (
                    ack[0] > 0
                    or any(value <= 0 for value in ack[1:])
                    or ack[1] > MAX_FRAME
                    or ack[2] > MAX_FRAME
                    or ack[3] > MAX_MESSAGE
                    or ack[4] > MAX_CHUNKS
                ):
                    raise ProtocolViolation("message_size_limit")
            if (
                self.message_type not in (None, message_type)
                or self.message_chunks >= MAX_CHUNKS
            ):
                raise ProtocolViolation("message_size_limit")
            frame = bytes(self.buffer[:size])
            del self.buffer[:size]
            self.message_type = message_type
            self.message_size += size
            self.message_chunks += 1
            if self.message_size > MAX_MESSAGE:
                raise ProtocolViolation("message_size_limit")
            frames.append(frame)
            if chunk_type in (ord("F"), ord("A")):
                self.message_size = 0
                self.message_chunks = 0
                self.message_type = None
        return frames


class RawSocketAdapter:
    def __init__(self, sock: Any, gate: RequestGate) -> None:
        self.sock = sock
        self.gate = gate
        self.loop = asyncio.get_running_loop()
        self.connected = True
        self.queue: asyncio.Queue[tuple[bytes, asyncio.Future[None], str] | None] = (
            asyncio.Queue(maxsize=1)
        )
        self.cancelled = asyncio.Event()
        self.deadline = time.monotonic() + 90
        self.hello_sent = False

    def write(self, data: bytes) -> None:
        if not self.connected or len(data) > MAX_MESSAGE:
            raise ProtocolViolation("message_size_limit")
        service = self.gate.armed_service
        if service is None:
            if not self.hello_sent and _is_bounded_hello(data):
                service = "Hello"
                self.hello_sent = True
            else:
                self.gate.stats.attempts += 1
                self.gate.stats.blocked += 1
                raise ProtocolViolation("service_not_allowed")
        self.gate.stats.attempts += 1
        receipt: asyncio.Future[None] = self.loop.create_future()
        self.last_receipt = receipt
        assert service is not None
        self.gate.armed_service = None
        self.gate.pending_service = None
        self.loop.call_soon(self._enqueue, (bytes(data), receipt, service))

    def _enqueue(self, item: tuple[bytes, asyncio.Future[None], str]) -> None:
        if self.queue.full():
            if not item[1].done():
                item[1].set_exception(ProtocolViolation("write_queue_full"))
            self.abort()
            return
        self.queue.put_nowait(item)

    async def writer(self) -> None:
        while self.connected:
            item = await self.queue.get()
            if item is None:
                return
            data, receipt, service = item
            send_started = False
            try:
                await self.gate.wait_admission(self.cancelled, self.deadline)
                frames = _split_frames(data)
                first = True
                for frame in frames:
                    send_started = True
                    await self.loop.sock_sendall(self.sock, frame)
                    self.gate.stats.bytes_sent += len(frame)
                    self.gate.stats.chunks_sent += 1
                    if first:
                        self.gate.stats.requests += 1
                        self.gate.stats.by_service[service] = (
                            self.gate.stats.by_service.get(service, 0) + 1
                        )
                        first = False
                self.gate.last_send = time.monotonic()
                if not receipt.done():
                    receipt.set_result(None)
            except BaseException as exc:
                if send_started:
                    self.gate.stats.request_count_known = False
                else:
                    self.gate.release_before_send(service)
                self.abort()
                if not receipt.done():
                    if isinstance(exc, asyncio.CancelledError):
                        receipt.cancel()
                    else:
                        receipt.set_exception(
                            ConnectionError("partial_send")
                            if isinstance(exc, OSError)
                            else exc
                        )
                raise

    def close(self) -> None:
        self.connected = False
        self.cancelled.set()
        self.sock.close()
        try:
            self.queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def abort(self) -> None:
        self.connected = False
        self.cancelled.set()
        self.sock.close()


class GuardedProtocol(UASocketProtocol):
    def __init__(self, adapter: RawSocketAdapter, timeout: float) -> None:
        super().__init__(
            timeout=timeout, limits=TransportLimits(65536, 65536, 16, 131072)
        )
        self.adapter = adapter
        self._receipts: list[asyncio.Future[None]] = []

    def connection_made(self, transport: Any) -> None:
        self.transport = transport

    async def send_hello(
        self,
        url: str,
        max_messagesize: int = MAX_MESSAGE,
        max_chunkcount: int = MAX_CHUNKS,
    ) -> Any:
        hello = ua.Hello(
            ProtocolVersion=0,
            ReceiveBufferSize=65536,
            SendBufferSize=65536,
            MaxMessageSize=131072,
            MaxChunkCount=16,
            EndpointUrl=url,
        )
        ack_future = asyncio.get_running_loop().create_future()
        self._callbackmap[0] = ack_future
        self.transport.write(uatcp_to_binary(ua.MessageType.Hello, hello))
        ack = await asyncio.wait_for(ack_future, self.timeout)
        await self.adapter.last_receipt
        return ack

    def _send_request(
        self,
        request: Any,
        timeout: float = 1,
        message_type: Any = ua.MessageType.SecureMessage,
    ) -> Any:
        name = type(request).__name__
        expected_message_type = EXPECTED_MESSAGE_TYPES.get(
            name, ua.MessageType.SecureMessage
        )
        if (
            ALLOWED_TYPES.get(name) is not type(request)
            or message_type != expected_message_type
        ):
            self.adapter.gate.stats.attempts += 1
            self.adapter.gate.stats.blocked += 1
            raise ProtocolViolation("service_not_allowed")
        object_id = getattr(ua.ObjectIds, f"{name}_Encoding_DefaultBinary", None)
        if object_id is None:
            self.adapter.gate.stats.blocked += 1
            raise ProtocolViolation("service_not_allowed")
        serial = self.adapter.gate.authorize(request, request.TypeId)
        self.adapter.gate.take(request, serial)
        try:
            source = super()._send_request(request, timeout, message_type)
        except BaseException:
            self.adapter.gate.disarm()
            self.adapter.gate.release_before_send(
                type(request).__name__.removesuffix("Request")
            )
            raise
        receipt = self.adapter.last_receipt
        self._receipts.append(receipt)
        result: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        async def relay() -> None:
            try:
                await asyncio.shield(receipt)
                value = await source
                if not result.done():
                    result.set_result(value)
            except BaseException as exc:
                if not result.done():
                    result.set_exception(exc)

        asyncio.create_task(relay())
        return result

    async def send_request(
        self,
        request: Any,
        timeout: float | None = None,
        message_type: Any = ua.MessageType.SecureMessage,
    ) -> Any:
        try:
            return await super().send_request(request, timeout, message_type)
        finally:
            if self._receipts:
                await asyncio.shield(self._receipts.pop(0))

    async def open_secure_channel(self, params: Any) -> Any:
        try:
            return await super().open_secure_channel(params)
        finally:
            if self._receipts:
                await asyncio.shield(self._receipts.pop(0))

    async def close_secure_channel(self) -> None:
        try:
            await super().close_secure_channel()
        finally:
            if self._receipts:
                await asyncio.shield(self._receipts.pop(0))


def _split_frames(data: bytes) -> list[bytes]:
    frames: list[bytes] = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 8:
            raise ProtocolViolation("message_size_limit")
        size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        if size < 8 or size > MAX_FRAME or offset + size > len(data):
            raise ProtocolViolation("message_size_limit")
        frames.append(data[offset : offset + size])
        offset += size
        if len(frames) > MAX_CHUNKS or offset > MAX_MESSAGE:
            raise ProtocolViolation("message_size_limit")
    return frames


def _is_bounded_hello(data: bytes) -> bool:
    if (
        len(data) < 32
        or data[:4] != b"HELF"
        or struct.unpack_from("<I", data, 4)[0] != len(data)
    ):
        return False
    protocol, receive, send, message, chunks, text_size = struct.unpack_from(
        "<6I", data, 8
    )
    return (
        protocol == 0
        and receive == 65536
        and send == 65536
        and message == MAX_MESSAGE
        and chunks == MAX_CHUNKS
        and text_size >= 0
        and len(data) == 32 + text_size
    )


def validate_target(host: str, port: int) -> tuple[str, int]:
    return str(ipaddress.IPv4Address(host)), min(max(int(port), 1), 65535)
