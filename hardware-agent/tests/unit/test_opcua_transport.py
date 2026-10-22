import asyncio
import socket
import struct
import time

import pytest
from agent.ot.opcua.guarded_transport import (
    BoundedFramer,
    GuardedProtocol,
    ProtocolViolation,
    RawSocketAdapter,
    RequestGate,
)
from agent.ot.opcua.worker import _sanitize_url
from asyncua import ua
from asyncua.common.utils import Buffer
from asyncua.ua.ua_binary import struct_from_binary, uatcp_to_binary


def test_ack_and_header_limits_are_checked_before_body_arrives() -> None:
    framer = BoundedFramer()
    with pytest.raises(ProtocolViolation):
        framer.feed(struct.pack("<3sBI", b"MSG", ord("F"), 131073))
    with pytest.raises(ProtocolViolation):
        BoundedFramer().feed(
            struct.pack("<3sBI", b"ACK", ord("F"), 28)
            + struct.pack("<5I", 0, 0, 1, 1, 1)
        )


def test_cumulative_wire_bytes_are_capped_across_completed_messages() -> None:
    frame = struct.pack("<3sBI", b"MSG", ord("F"), 65536) + bytes(65528)
    framer = BoundedFramer()
    for _ in range(64):
        framer.feed(frame)
    with pytest.raises(ProtocolViolation):
        framer.feed(frame)


def test_chunk_accumulation_caps_at_sixteen_and_resets_on_final() -> None:
    framer = BoundedFramer()

    def chunk(kind: str) -> bytes:
        return struct.pack("<3sBI", b"MSG", ord(kind), 8)

    for _ in range(16):
        framer.feed(chunk("C"))
    with pytest.raises(ProtocolViolation):
        framer.feed(chunk("C"))
    framer = BoundedFramer()
    framer.feed(chunk("C") * 15 + chunk("F"))
    assert framer.feed(chunk("F"))
    with pytest.raises(ProtocolViolation):
        BoundedFramer().feed(struct.pack("<3sBI", b"HEL", ord("C"), 8))
    with pytest.raises(ProtocolViolation):
        framer.feed(chunk("C") + struct.pack("<3sBI", b"OPN", ord("F"), 8))


def test_request_gate_checks_exact_class_and_keeps_cleanup_one_shot() -> None:
    gate = RequestGate(4)
    with pytest.raises(ProtocolViolation):
        gate.authorize(
            ua.WriteRequest(),
            ua.NodeId(ua.ObjectIds.WriteRequest_Encoding_DefaultBinary),
        )
    with pytest.raises(ProtocolViolation):
        gate.authorize(
            ua.GetEndpointsRequest(),
            ua.NodeId(ua.ObjectIds.ReadRequest_Encoding_DefaultBinary),
        )
    gate.authorize(
        ua.CloseSessionRequest(),
        ua.NodeId(ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary),
    )
    with pytest.raises(ProtocolViolation):
        gate.authorize(
            ua.CloseSessionRequest(),
            ua.NodeId(ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary),
        )


def test_cleanup_reservations_are_independent_and_ordinary_budget_stops_early() -> None:
    gate = RequestGate(2)
    for request in (ua.GetEndpointsRequest(), ua.OpenSecureChannelRequest()):
        with pytest.raises(ProtocolViolation):
            gate.authorize(
                request,
                ua.NodeId(
                    getattr(
                        ua.ObjectIds,
                        f"{type(request).__name__}_Encoding_DefaultBinary",
                    )
                ),
            )
    for cls in (ua.CloseSessionRequest, ua.CloseSecureChannelRequest):
        request = cls()
        type_id = ua.NodeId(
            getattr(ua.ObjectIds, f"{cls.__name__}_Encoding_DefaultBinary")
        )
        gate.authorize(request, type_id)
        gate.take(request, gate._serial)
        gate.disarm()
    for cls in (ua.CloseSessionRequest, ua.CloseSecureChannelRequest):
        with pytest.raises(ProtocolViolation):
            gate.authorize(
                cls(),
                ua.NodeId(
                    getattr(ua.ObjectIds, f"{cls.__name__}_Encoding_DefaultBinary")
                ),
            )


@pytest.mark.asyncio
async def test_direct_guard_rejects_wrong_kind_and_matching_subclass_name() -> None:
    left, right = socket.socketpair()
    left.setblocking(False)
    adapter = RawSocketAdapter(left, RequestGate(8))
    protocol = GuardedProtocol(adapter, 1)
    protocol.connection_made(adapter)
    writer = asyncio.create_task(adapter.writer())
    with pytest.raises(ProtocolViolation):
        protocol._send_request(
            ua.GetEndpointsRequest(), message_type=ua.MessageType.SecureOpen
        )
    blocked_before_subclass = adapter.gate.stats.blocked

    class GetEndpointsRequest(ua.GetEndpointsRequest):
        pass

    with pytest.raises(ProtocolViolation):
        protocol._send_request(GetEndpointsRequest())
    assert adapter.gate.stats.attempts == 2
    assert adapter.gate.stats.blocked == blocked_before_subclass + 1
    assert adapter.gate.stats.requests == 0
    assert adapter.gate.stats.bytes_sent == 0
    assert adapter.gate.stats.chunks_sent == 0
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.get_running_loop().sock_recv(right, 1), 0.05)
    adapter.abort()
    writer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writer
    right.close()


@pytest.mark.asyncio
async def test_direct_guard_checks_mutated_request_type_id_before_wire_write() -> None:
    left, right = socket.socketpair()
    left.setblocking(False)
    adapter = RawSocketAdapter(left, RequestGate(8))
    protocol = GuardedProtocol(adapter, 1)
    protocol.connection_made(adapter)
    writer = asyncio.create_task(adapter.writer())
    request = ua.GetEndpointsRequest()
    request.TypeId = ua.NodeId(ua.ObjectIds.WriteRequest_Encoding_DefaultBinary)
    with pytest.raises(ProtocolViolation):
        protocol._send_request(request)
    assert adapter.gate.stats.requests == 0
    assert adapter.gate.stats.blocked == 1
    assert adapter.gate.stats.bytes_sent == 0
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.get_running_loop().sock_recv(right, 1), 0.05)
    adapter.abort()
    writer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writer
    right.close()


def test_worker_url_sanitizer_drops_credentials_and_untrusted_destinations() -> None:
    assert (
        _sanitize_url("opc.tcp://127.0.0.1:4840/safe_path", "127.0.0.1", 4840)
        == "opc.tcp://127.0.0.1:4840/safe_path"
    )
    assert (
        _sanitize_url("opc.tcp://user:secret@127.0.0.1:4840/path", "127.0.0.1", 4840)
        == ""
    )
    assert _sanitize_url("opc.tcp://192.0.2.1:4840/path", "127.0.0.1", 4840) == ""


@pytest.mark.asyncio
async def test_raw_socket_writer_waits_for_send_receipt_and_counts_wire_bytes() -> None:
    left, right = socket.socketpair()
    left.setblocking(False)
    right.setblocking(False)
    adapter = RawSocketAdapter(left, RequestGate(4))
    task = asyncio.create_task(adapter.writer())
    frame = uatcp_to_binary(
        ua.MessageType.Hello,
        ua.Hello(
            ReceiveBufferSize=65536,
            SendBufferSize=65536,
            MaxMessageSize=131072,
            MaxChunkCount=16,
            EndpointUrl="opc.tcp://127.0.0.1:4840",
        ),
    )
    adapter.write(frame)
    await asyncio.wait_for(adapter.last_receipt, 1)
    assert await asyncio.get_running_loop().sock_recv(right, len(frame)) == frame
    assert adapter.gate.stats.requests == 1
    assert adapter.gate.stats.bytes_sent == len(frame)
    adapter.abort()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    right.close()


@pytest.mark.asyncio
async def test_protocol_sends_the_exact_bounded_hello() -> None:
    left, right = socket.socketpair()
    left.setblocking(False)
    right.setblocking(False)
    adapter = RawSocketAdapter(left, RequestGate(8))
    protocol = GuardedProtocol(adapter, 1)
    protocol.connection_made(adapter)
    writer = asyncio.create_task(adapter.writer())
    hello_task = asyncio.create_task(protocol.send_hello("opc.tcp://127.0.0.1:4840"))
    header = await asyncio.get_running_loop().sock_recv(right, 8)
    size = struct.unpack("<I", header[4:8])[0]
    payload = header + await asyncio.get_running_loop().sock_recv(right, size - 8)
    hello = struct_from_binary(ua.Hello, Buffer(payload[8:]))
    assert (
        hello.ReceiveBufferSize,
        hello.SendBufferSize,
        hello.MaxMessageSize,
        hello.MaxChunkCount,
    ) == (65536, 65536, 131072, 16)
    ack = ua.Acknowledge(
        ProtocolVersion=0,
        ReceiveBufferSize=65536,
        SendBufferSize=65536,
        MaxMessageSize=131072,
        MaxChunkCount=16,
    )
    frame = uatcp_to_binary(ua.MessageType.Acknowledge, ack)
    for ready in BoundedFramer().feed(frame):
        protocol.data_received(ready)
    await hello_task
    adapter.abort()
    writer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writer
    right.close()


@pytest.mark.asyncio
async def test_partial_socket_send_aborts_and_marks_count_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    left, right = socket.socketpair()
    left.setblocking(False)
    adapter = RawSocketAdapter(left, RequestGate(8))
    loop = asyncio.get_running_loop()

    async def partial(sock: socket.socket, data: bytes) -> None:
        raise OSError("partial")

    monkeypatch.setattr(loop, "sock_sendall", partial)
    writer = asyncio.create_task(adapter.writer())
    adapter.write(
        uatcp_to_binary(
            ua.MessageType.Hello,
            ua.Hello(
                ReceiveBufferSize=65536,
                SendBufferSize=65536,
                MaxMessageSize=131072,
                MaxChunkCount=16,
                EndpointUrl="opc.tcp://127.0.0.1:4840",
            ),
        )
    )
    with pytest.raises(ConnectionError):
        await adapter.last_receipt
    with pytest.raises(OSError):
        await writer
    assert adapter.gate.stats.requests == 0
    assert adapter.gate.stats.request_count_known is False
    assert adapter.connected is False
    right.close()


@pytest.mark.asyncio
async def test_adapter_rejects_unpermitted_direct_transport_write() -> None:
    left, right = socket.socketpair()
    left.setblocking(False)
    adapter = RawSocketAdapter(left, RequestGate(8))
    with pytest.raises(ProtocolViolation):
        adapter.write(struct.pack("<3sBI", b"MSG", ord("F"), 8))
    assert adapter.gate.stats.blocked == 1
    assert adapter.gate.stats.requests == 0
    adapter.abort()
    right.close()


@pytest.mark.asyncio
async def test_pacing_wait_is_cancellable_and_at_least_one_hundred_ms() -> None:
    gate = RequestGate(8)
    gate.last_send = time.monotonic()
    started = time.monotonic()
    await gate.wait_admission(asyncio.Event(), time.monotonic() + 1)
    assert time.monotonic() - started >= 0.095
    cancelled = asyncio.Event()
    cancelled.set()
    with pytest.raises(asyncio.CancelledError):
        await gate.wait_admission(cancelled, time.monotonic() + 1)
