from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import socket
import sys
import time
from typing import Any
from urllib.parse import urlsplit

from asyncua import Client, ua

from .bounded_decode import install
from .guarded_transport import (
    BoundedFramer,
    GuardedProtocol,
    ProtocolViolation,
    RawSocketAdapter,
    RequestGate,
    validate_target,
)
from .worker_mapping import run_mapping

MAX_COMMAND = 4096
MAX_RESPONSE = 128 * 1024


def _response(code: str, stats: Any | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "error", "code": code}
    if stats is not None:
        result.update(
            requests=stats.by_service,
            requests_total=stats.requests,
            write_requests_sent=stats.by_service.get("Write", 0),
            request_attempts=stats.attempts,
            requests_blocked=stats.blocked,
            bytes_sent=stats.bytes_sent,
            bytes_received=stats.bytes_received,
            chunks_sent=stats.chunks_sent,
            chunks_received=stats.chunks_received,
            request_count_known=stats.request_count_known,
            hello_limits=[65536, 65536, 131072, 16],
        )
    return result


def _safe_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value[:limit] if char.isprintable())


def _endpoint(endpoint: Any, host: str, port: int) -> dict[str, Any]:
    policy = _safe_text(endpoint.SecurityPolicyUri, 256)
    mode = {"None_": "None"}.get(
        getattr(endpoint.SecurityMode, "name", ""),
        getattr(endpoint.SecurityMode, "name", ""),
    )[:32]
    profile = _safe_text(endpoint.TransportProfileUri, 128)
    token_types = []
    for token in endpoint.UserIdentityTokens[:8]:
        token_name = getattr(token.TokenType, "name", "")
        if token_name in {"Anonymous", "UserName", "Certificate", "IssuedToken"}:
            token_types.append(token_name)
    server = endpoint.Server
    certificate = endpoint.ServerCertificate
    fingerprint = (
        hashlib.sha256(certificate).hexdigest()
        if isinstance(certificate, bytes) and len(certificate) <= 65536
        else None
    )
    return {
        "endpoint_url": _sanitize_url(endpoint.EndpointUrl, host, port),
        "security_policy": policy,
        "security_mode": mode,
        "transport_profile": profile,
        "security_level": min(max(int(endpoint.SecurityLevel), 0), 255),
        "user_token_count": min(len(endpoint.UserIdentityTokens), 8),
        "user_token_types": token_types,
        "application_uri": _safe_text(server.ApplicationUri, 128) or None,
        "product_uri": _safe_text(server.ProductUri, 128) or None,
        "application_name": _safe_text(
            getattr(getattr(server, "ApplicationName", None), "Text", ""), 128
        )
        or None,
        "application_type": getattr(server.ApplicationType, "name", "")[:32] or None,
        "certificate_sha256": fingerprint,
    }


def _sanitize_url(value: Any, host: str, port: int) -> str:
    if not isinstance(value, str) or len(value) > 1024:
        return ""
    try:
        parsed = urlsplit(value)
        target_port = parsed.port or 4840
        path = parsed.path or "/"
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "opc.tcp"
        or parsed.hostname != host
        or target_port != port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or len(path) > 256
        or re.fullmatch(r"/[A-Za-z0-9/_.-]*", path) is None
    ):
        return ""
    return f"opc.tcp://{host}:{port}{path}"


def _stats_fields(stats: Any) -> dict[str, Any]:
    request_counts = dict(stats.by_service)
    if "Hello" in request_counts:
        request_counts["HEL"] = request_counts.pop("Hello")
    return {
        "requests": request_counts,
        "requests_total": stats.requests,
        "write_requests_sent": stats.by_service.get("Write", 0),
        "request_attempts": stats.attempts,
        "requests_blocked": stats.blocked,
        "bytes_sent": stats.bytes_sent,
        "bytes_received": stats.bytes_received,
        "chunks_sent": stats.chunks_sent,
        "chunks_received": stats.chunks_received,
        "request_count_known": stats.request_count_known,
        "hello_limits": [65536, 65536, 131072, 16],
    }


def _retain_mapping_on_cleanup_failure(
    response: dict[str, Any] | None, code: str
) -> dict[str, Any] | None:
    if response is None or not isinstance(response.get("mapping"), dict):
        return None
    mapping = response["mapping"]
    phase = mapping["phase"]
    phase["status"] = "partial"
    phase["truncated"] = True
    reason = (
        code
        if code in {"timeout", "request_budget_exhausted", "message_size_limit"}
        else "service_error"
    )
    reasons = phase.setdefault("reason_codes", [])
    if reason not in reasons:
        reasons.append(reason)
    response["status"] = "ok"
    return response


async def execute(command: dict[str, Any]) -> dict[str, Any]:
    operation = command.get("operation")
    if operation not in {"get_endpoints", "probe_read_only", "map_anonymous"}:
        return _response("unsupported_operation")
    try:
        if isinstance(command.get("port"), bool) or not isinstance(
            command.get("port"), int
        ):
            return _response("invalid_request")
        for field, default in (
            ("request_budget", None),
            ("timeout_ms", None),
            ("pacing_ms", 100),
            ("deadline_ms", 90000),
        ):
            value = command.get(field, default)
            if isinstance(value, bool) or not isinstance(value, int):
                return _response("invalid_request")
        if not isinstance(command.get("host"), str):
            return _response("invalid_request")
        host, port = validate_target(command["host"], command["port"])
        budget = min(max(int(command["request_budget"]), 0), 32)
        timeout = min(max(int(command["timeout_ms"]), 1), 2000) / 1000
        pacing = min(max(int(command.get("pacing_ms", 100)), 100), 2000) / 1000
        deadline = (
            time.monotonic()
            + min(max(int(command.get("deadline_ms", 90000)), 1), 90000) / 1000
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return _response("invalid_request")
    if budget < 5:
        return _response("request_budget_exhausted")
    try:
        install()
    except Exception:
        return _response("service_error")
    gate = RequestGate(budget, pacing)
    url = f"opc.tcp://{host}:{port}"
    client = Client(url, timeout=timeout)
    client.max_messagesize = 131072
    client.max_chunkcount = 16
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    adapter: RawSocketAdapter | None = None
    reader_task: asyncio.Task[None] | None = None
    writer_task: asyncio.Task[None] | None = None
    response: dict[str, Any]
    response = None
    reader_violation: ProtocolViolation | None = None
    try:
        async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
            await asyncio.wait_for(
                asyncio.get_running_loop().sock_connect(sock, (host, port)), timeout
            )
            adapter = RawSocketAdapter(sock, gate)
            adapter.deadline = deadline
            protocol = GuardedProtocol(adapter, timeout)
            protocol.connection_made(adapter)
            client.uaclient.protocol = protocol

            async def read_socket() -> None:
                nonlocal reader_violation
                framer = BoundedFramer()
                try:
                    while adapter is not None and adapter.connected:
                        data = await asyncio.get_running_loop().sock_recv(sock, 65536)
                        if not data:
                            raise ConnectionError("peer_closed")
                        gate.stats.bytes_received += len(data)
                        for frame in framer.feed(data):
                            gate.stats.chunks_received += 1
                            protocol.data_received(frame)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    if isinstance(error, ProtocolViolation):
                        reader_violation = error
                    if adapter is not None:
                        adapter.abort()
                    protocol.connection_lost(error)

            reader_task = asyncio.create_task(read_socket())
            writer_task = asyncio.create_task(adapter.writer())
            await client.send_hello()
            await client.open_secure_channel()
            endpoints = await client.uaclient.get_endpoints(
                ua.GetEndpointsParameters(EndpointUrl=url)
            )
            selected_endpoint = None
            selected_index = -1
            if operation == "map_anonymous":
                requested = command.get("endpoint_url")
                if not isinstance(requested, str) or len(requested) > 320:
                    raise ValueError("invalid_endpoint")
                for index, item in enumerate(endpoints[:16]):
                    if (
                        item.SecurityPolicyUri
                        == "http://opcfoundation.org/UA/SecurityPolicy#None"
                        and item.SecurityMode == ua.MessageSecurityMode.None_
                        and any(
                            token.TokenType == ua.UserTokenType.Anonymous
                            for token in item.UserIdentityTokens
                        )
                        and _sanitize_url(item.EndpointUrl, host, port) == requested
                    ):
                        selected_endpoint, selected_index = item, index
                        break
                if selected_endpoint is None:
                    await asyncio.wait_for(
                        client.uaclient.protocol.close_secure_channel(),
                        min(1.0, max(0.001, deadline - time.monotonic())),
                    )
                    response = {
                        "status": "error",
                        "code": "service_error",
                        **_stats_fields(gate.stats),
                    }
                else:
                    mapped = await run_mapping(
                        client, selected_endpoint, selected_index, timeout
                    )
                    response = {
                        "status": "ok",
                        "mapping": mapped,
                        **_stats_fields(gate.stats),
                    }
                    response = _fit_mapping_response(response)
                    if adapter.connected and time.monotonic() < deadline:
                        await asyncio.wait_for(
                            client.uaclient.protocol.close_secure_channel(),
                            min(1.0, max(0.001, deadline - time.monotonic())),
                        )
            else:
                safe = [_endpoint(item, host, port) for item in endpoints[:16]]
                if operation == "probe_read_only":
                    await _probe_read_only(client)
                await asyncio.wait_for(
                    client.uaclient.protocol.close_secure_channel(),
                    min(1.0, max(0.001, deadline - time.monotonic())),
                )
                response = {
                    "status": "ok",
                    "endpoints": safe,
                    "endpoints_truncated": len(endpoints) > 16,
                    **_stats_fields(gate.stats),
                }
    except TimeoutError:
        response = _retain_mapping_on_cleanup_failure(response, "timeout") or _response(
            "timeout"
        )
    except asyncio.CancelledError:
        raise
    except ProtocolViolation as error:
        code = str(error)
        if code not in {
            "message_size_limit",
            "request_budget_exhausted",
            "service_not_allowed",
        }:
            code = "service_error"
        response = _retain_mapping_on_cleanup_failure(response, code) or _response(code)
    except Exception:
        code = (
            str(reader_violation) if reader_violation is not None else "service_error"
        )
        if code not in {
            "message_size_limit",
            "request_budget_exhausted",
            "service_not_allowed",
        }:
            code = "service_error"
        response = _retain_mapping_on_cleanup_failure(response, code) or _response(code)
    finally:
        if adapter is not None:
            adapter.abort()
        tasks = [task for task in (reader_task, writer_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            with contextlib.suppress(
                asyncio.TimeoutError, asyncio.CancelledError, Exception
            ):
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), 0.1
                )
        sock.close()
    if gate is not None:
        response.update(_stats_fields(gate.stats))
    return response


def main() -> int:
    logging.disable(logging.CRITICAL)
    raw = sys.stdin.buffer.read(MAX_COMMAND + 1)
    if len(raw) > MAX_COMMAND:
        response = _response("invalid_request")
    else:
        try:
            command = json.loads(raw)
            response = (
                asyncio.run(execute(command))
                if isinstance(command, dict)
                else _response("invalid_request")
            )
        except Exception:
            response = _response("invalid_request")
    payload = json.dumps(response, separators=(",", ":"), ensure_ascii=True).encode()
    if len(payload) > MAX_RESPONSE:
        payload = b'{"status":"error","code":"message_size_limit"}'
    sys.stdout.buffer.write(payload)
    return 0


async def _probe_read_only(client: Client) -> None:
    """Exercise the three guarded metadata services used by the transport harness."""
    protocol = client.uaclient.protocol
    requests = (
        (
            ua.BrowseRequest,
            ua.BrowseResponse,
            ua.BrowseParameters(
                View=ua.ViewDescription(),
                RequestedMaxReferencesPerNode=16,
                NodesToBrowse=[
                    ua.BrowseDescription(
                        NodeId=ua.NodeId(85),
                        BrowseDirection=ua.BrowseDirection.Forward,
                        ReferenceTypeId=ua.NodeId(31),
                        IncludeSubtypes=True,
                        ResultMask=int(ua.BrowseResultMask.BrowseName),
                    )
                ],
            ),
        ),
        (
            ua.BrowseNextRequest,
            ua.BrowseNextResponse,
            ua.BrowseNextParameters(
                ReleaseContinuationPoints=False, ContinuationPoints=[]
            ),
        ),
        (
            ua.ReadRequest,
            ua.ReadResponse,
            ua.ReadParameters(
                MaxAge=0,
                TimestampsToReturn=ua.TimestampsToReturn.Neither,
                NodesToRead=[
                    ua.ReadValueId(
                        NodeId=ua.NodeId(2253), AttributeId=ua.AttributeIds.BrowseName
                    )
                ],
            ),
        ),
    )
    for request_type, response_type, parameters in requests:
        request = request_type()
        request.Parameters = parameters
        try:
            raw = await protocol.send_request(request)
            ua.ua_binary.struct_from_binary(response_type, raw)
        except Exception:
            # Probe responses may be ServiceFaults before a session exists. The harness
            # still requires the fixed Browse, BrowseNext and Read attempts.
            continue


def _fit_mapping_response(response: dict[str, Any]) -> dict[str, Any]:
    mapping = response["mapping"]
    while (
        len(json.dumps(response, separators=(",", ":"), ensure_ascii=True).encode())
        > MAX_RESPONSE
    ):
        mapping["phase"]["status"] = "partial"
        mapping["phase"]["truncated"] = True
        reasons = mapping["phase"].setdefault("reason_codes", [])
        if "observation_size_limit" not in reasons:
            reasons.append("observation_size_limit")
        if mapping["references"]:
            mapping["references"].pop()
        elif mapping["nodes"]:
            removed = mapping["nodes"].pop()
            if removed.get("value_read_status") == "Good":
                mapping["value_good_count"] = max(0, mapping["value_good_count"] - 1)
            mapping["application_value_read_succeeded"] = None
        else:
            return _response("message_size_limit")
    return response


if __name__ == "__main__":
    raise SystemExit(main())
