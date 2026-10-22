from __future__ import annotations

import asyncio
import ipaddress
import json
import sys
from typing import Any

from .models import (
    OpcUaClientResult,
    OpcUaEndpoint,
    OpcUaMappedNode,
    OpcUaMappedReference,
    OpcUaMappingResult,
    OpcUaRequestStats,
)

MAX_REQUEST_BUDGET = 32
MAX_OPERATION_TIMEOUT_SECONDS = 2.0
# The helper's network timeout remains independently capped at two seconds. This
# grace only bounds how long the parent allows a cold worker process to start
# and return its result; it is not part of the OPC UA operation timeout.
HELPER_STARTUP_GRACE_SECONDS = 4.0
_ERRORS: set[str] = {
    "invalid_target",
    "unsupported_operation",
    "timeout",
    "message_size_limit",
    "request_budget_exhausted",
    "service_not_allowed",
    "service_error",
    "helper_unavailable",
    "invalid_request",
}


class OpcUaClient:
    """Narrow metadata-only IPC facade; never returns SDK or value objects."""

    async def discover_endpoints(
        self,
        host: str,
        port: int,
        *,
        request_budget: int = MAX_REQUEST_BUDGET,
        timeout: float = MAX_OPERATION_TIMEOUT_SECONDS,
        pacing_ms: int = 100,
    ) -> OpcUaClientResult:
        try:
            target = ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:
            return OpcUaClientResult("error", error="invalid_target")
        if not 1 <= port <= 65535:
            return OpcUaClientResult("error", error="invalid_target")

        return await self._invoke(
            "get_endpoints",
            str(target),
            port,
            request_budget=request_budget,
            timeout=timeout,
            pacing_ms=pacing_ms,
        )

    async def probe_read_only_services(
        self,
        host: str,
        port: int,
        *,
        request_budget: int = MAX_REQUEST_BUDGET,
        timeout: float = MAX_OPERATION_TIMEOUT_SECONDS,
    ) -> OpcUaClientResult:
        """Send fixed metadata-only service requests for harness checks."""
        try:
            target = ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:
            return OpcUaClientResult("error", error="invalid_target")
        if not 1 <= port <= 65535:
            return OpcUaClientResult("error", error="invalid_target")

        return await self._invoke(
            "probe_read_only",
            str(target),
            port,
            request_budget=request_budget,
            timeout=timeout,
            overall_timeout=10.0,
        )

    async def map_anonymous(
        self,
        host: str,
        port: int,
        endpoint: OpcUaEndpoint,
        *,
        request_budget: int = MAX_REQUEST_BUDGET,
        timeout: float = MAX_OPERATION_TIMEOUT_SECONDS,
        deadline: float = 90.0,
        pacing_ms: int = 100,
    ) -> OpcUaClientResult:
        """Map one explicitly anonymous None endpoint in the helper process."""
        try:
            target = ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:
            return OpcUaClientResult("error", error="invalid_target")
        if not 1 <= port <= 65535:
            return OpcUaClientResult("error", error="invalid_target")
        if (
            endpoint.security_policy_uri
            != "http://opcfoundation.org/UA/SecurityPolicy#None"
            or endpoint.security_mode != "None"
            or "Anonymous" not in endpoint.user_token_types
            or not endpoint.endpoint_url
        ):
            return OpcUaClientResult("error", error="unsupported_operation")
        budget = min(max(int(request_budget), 1), MAX_REQUEST_BUDGET)
        timeout_ms = min(max(int(timeout * 1000), 1), 2000)
        return await self._invoke(
            "map_anonymous",
            str(target),
            port,
            request_budget=budget,
            timeout=timeout_ms / 1000,
            overall_timeout=min(max(float(deadline), 0.1), 90.0),
            pacing_ms=pacing_ms,
            endpoint_url=endpoint.endpoint_url,
        )

    async def _invoke(
        self,
        operation: str,
        host: str,
        port: int,
        *,
        request_budget: int,
        timeout: float,
        endpoint_url: str | None = None,
        overall_timeout: float | None = None,
        pacing_ms: int = 100,
    ) -> OpcUaClientResult:

        budget = min(max(int(request_budget), 1), MAX_REQUEST_BUDGET)
        timeout_ms = min(max(int(timeout * 1000), 1), 2000)
        request = json.dumps(
            {
                "operation": operation,
                "host": host,
                "port": port,
                "request_budget": budget,
                "timeout_ms": timeout_ms,
                "pacing_ms": min(max(int(pacing_ms), 100), 2000),
                "deadline_ms": min(
                    max(
                        int((overall_timeout or (timeout_ms / 1000)) * 1000),
                        1,
                    ),
                    90000,
                ),
                **({"endpoint_url": endpoint_url} if endpoint_url else {}),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            command = _helper_command()
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except (OSError, RuntimeError):
            return OpcUaClientResult("error", error="helper_unavailable")

        try:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(request)
            await process.stdin.drain()
            process.stdin.close()
            stdout = await asyncio.wait_for(
                _finish_worker(process, process.stdout),
                timeout=(
                    overall_timeout
                    if overall_timeout is not None
                    else min(
                        timeout_ms / 1000 + HELPER_STARTUP_GRACE_SECONDS,
                        30.0,
                    )
                ),
            )
            if len(stdout) > 128 * 1024:
                return OpcUaClientResult("error", error="invalid_response")
        except (asyncio.TimeoutError, asyncio.CancelledError):
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            if isinstance(sys.exc_info()[1], asyncio.CancelledError):
                raise
            return OpcUaClientResult(
                "error", error="timeout", request_count_known=False
            )

        try:
            response = json.loads(stdout)
            stats = _parse_stats(response)
            if response.get("status") == "ok":
                if operation == "map_anonymous":
                    return OpcUaClientResult(
                        "ok",
                        mapping=_parse_mapping(response.get("mapping")),
                        stats=stats,
                        request_count_known=response.get("request_count_known")
                        is not False,
                    )
                if operation == "probe_read_only":
                    return OpcUaClientResult(
                        "ok",
                        stats=stats,
                        request_count_known=response.get("request_count_known")
                        is not False,
                    )
                endpoints = tuple(
                    _parse_endpoint(item) for item in response["endpoints"]
                )
                endpoints_truncated = response.get("endpoints_truncated", False)
                if not isinstance(endpoints_truncated, bool):
                    return OpcUaClientResult("error", error="invalid_response")
                return OpcUaClientResult(
                    "ok",
                    endpoints=endpoints,
                    endpoints_truncated=endpoints_truncated,
                    stats=stats,
                    request_count_known=response.get("request_count_known")
                    is not False,
                )
            error = response.get("code")
            if error not in _ERRORS:
                error = "service_error"
            return OpcUaClientResult(
                "error",
                error=error,
                stats=stats,
                request_count_known=response.get("request_count_known") is not False,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return OpcUaClientResult("error", error="invalid_response")


def _helper_command() -> list[str]:
    return [sys.executable, "-m", "agent.ot.opcua.worker"]


async def _read_bounded(stream: asyncio.StreamReader, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(min(8192, limit + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            return b"".join(chunks)


async def _finish_worker(
    process: asyncio.subprocess.Process, stream: asyncio.StreamReader
) -> bytes:
    output = await _read_bounded(stream, 128 * 1024)
    if len(output) > 128 * 1024:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()
    return output


def _parse_stats(response: dict[str, Any]) -> OpcUaRequestStats:
    raw_counts = response.get("requests", {})
    if not isinstance(raw_counts, dict):
        raise TypeError("invalid request counters")
    counts = {
        str(name)[:64]: min(max(int(value), 0), MAX_REQUEST_BUDGET)
        for name, value in list(raw_counts.items())[:16]
    }
    raw_hello_limits = response.get("hello_limits")
    hello_limits = None
    if isinstance(raw_hello_limits, list) and len(raw_hello_limits) == 4:
        hello_limits = tuple(
            min(max(int(value), 0), 4 * 1024 * 1024) for value in raw_hello_limits
        )
    return OpcUaRequestStats(
        requests=counts,
        requests_total=min(
            max(int(response.get("requests_total", 0)), 0), MAX_REQUEST_BUDGET
        ),
        write_requests_sent=min(
            max(int(response.get("write_requests_sent", 0)), 0), MAX_REQUEST_BUDGET
        ),
        bytes_sent=min(max(int(response.get("bytes_sent", 0)), 0), 4 * 1024 * 1024),
        bytes_received=min(
            max(int(response.get("bytes_received", 0)), 0), 4 * 1024 * 1024
        ),
        hello_limits=hello_limits,
    )


def _parse_endpoint(value: Any) -> OpcUaEndpoint:
    if not isinstance(value, dict):
        raise TypeError("invalid endpoint")
    return OpcUaEndpoint(
        endpoint_url=_safe_text(value.get("endpoint_url"), 256),
        security_policy_uri=_safe_text(value.get("security_policy"), 256),
        security_mode=_safe_text(value.get("security_mode"), 32),
        transport_profile_uri=_safe_text(value.get("transport_profile"), 128),
        security_level=min(max(int(value.get("security_level", 0)), 0), 255),
        user_token_count=min(max(int(value.get("user_token_count", 0)), 0), 8),
        user_token_types=(
            tuple(
                text
                for item in value.get("user_token_types", [])[:8]
                if (text := _safe_text(item, 32))
                in {"Anonymous", "UserName", "Certificate", "IssuedToken"}
            )
            if isinstance(value.get("user_token_types", []), list)
            else ()
        ),
        application_uri=_safe_optional(value.get("application_uri"), 128),
        product_uri=_safe_optional(value.get("product_uri"), 128),
        application_name=_safe_optional(value.get("application_name"), 128),
        application_type=_safe_optional(
            value.get("application_type"),
            32,
            {"Server", "Client", "ClientAndServer", "DiscoveryServer"},
        ),
        certificate_sha256=_safe_optional(
            value.get("certificate_sha256"), 64, pattern="hex64"
        ),
    )


def _parse_mapping(value: Any) -> OpcUaMappingResult:
    if not isinstance(value, dict):
        raise TypeError("invalid mapping")
    statuses = {
        "completed",
        "partial",
        "denied",
        "unsupported_security",
        "failed",
        "timed_out",
        "skipped",
    }
    phase = value.get("phase", {})
    if not isinstance(phase, dict):
        raise TypeError("invalid mapping phase")
    status = phase.get("status")
    if status not in statuses:
        raise ValueError("invalid mapping status")
    allowed_reasons = {
        "timeout",
        "request_budget_exhausted",
        "service_error",
        "invalid_response",
        "message_size_limit",
        "service_not_allowed",
        "authentication_required",
        "anonymous_denied",
        "security_configuration_required",
        "external_reference",
        "page_limit",
        "node_limit",
        "depth_limit",
        "decode_limit",
        "opaque_node_id_omitted",
        "observation_size_limit",
        "decode_error",
        "byte_limit",
        "no_eligible_variables",
        "cancelled",
        "host_deadline",
        "stage_deadline",
        "global_deadline",
    }
    reasons = tuple(
        reason
        for reason in phase.get("reason_codes", [])[:16]
        if reason in allowed_reasons
    )
    nodes: list[OpcUaMappedNode] = []
    raw_nodes = value.get("nodes", [])
    if not isinstance(raw_nodes, list) or len(raw_nodes) > 128:
        raise TypeError("invalid mapping nodes")
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_class = item.get("node_class")
        if node_class not in {"Object", "Variable"}:
            continue
        nodes.append(
            OpcUaMappedNode(
                node_id=_safe_text(item.get("node_id"), 256),
                parent_node_id=_safe_optional(item.get("parent_node_id"), 256),
                depth=min(max(int(item.get("depth", 0)), 0), 4),
                node_class=node_class,
                browse_name=_safe_optional(item.get("browse_name"), 128),
                display_name=_safe_optional(item.get("display_name"), 128),
                data_type=_safe_optional(item.get("data_type"), 256),
                value_rank=(
                    min(max(int(item["value_rank"]), -(2**31)), 2**31 - 1)
                    if isinstance(item.get("value_rank"), int)
                    else None
                ),
                access_level=(
                    min(max(int(item["access_level"]), 0), 255)
                    if isinstance(item.get("access_level"), int)
                    else None
                ),
                user_access_level=(
                    min(max(int(item["user_access_level"]), 0), 255)
                    if isinstance(item.get("user_access_level"), int)
                    else None
                ),
                value_read_status=(
                    item.get("value_read_status")
                    if item.get("value_read_status")
                    in {"Good", "Denied", "Error", "Skipped"}
                    else None
                ),
            )
        )
    raw_references = value.get("references", [])
    if not isinstance(raw_references, list) or len(raw_references) > 512:
        raise TypeError("invalid mapping references")
    return OpcUaMappingResult(
        status=status,
        reason_codes=reasons,
        nodes=tuple(nodes),
        references=tuple(
            OpcUaMappedReference(
                source_node_id=_safe_text(reference.get("source_node_id"), 256),
                target_node_id=_safe_text(reference.get("target_node_id"), 256),
                reference_type_id=_safe_text(reference.get("reference_type_id"), 256),
                is_forward=reference.get("is_forward") is True,
            )
            for reference in raw_references
            if isinstance(reference, dict)
        ),
        references_observed=min(max(int(value.get("references_observed", 0)), 0), 512),
        value_reads_attempted=min(
            max(int(value.get("value_reads_attempted", 0)), 0), 8
        ),
        selected_endpoint_index=(
            min(max(int(value["selected_endpoint_index"]), 0), 15)
            if isinstance(value.get("selected_endpoint_index"), int)
            else None
        ),
        anonymous_session_activated=(
            value.get("anonymous_session_activated")
            if isinstance(value.get("anonymous_session_activated"), bool)
            else None
        ),
        browse_succeeded=(
            value.get("browse_succeeded")
            if isinstance(value.get("browse_succeeded"), bool)
            else None
        ),
        application_value_read_succeeded=(
            value.get("application_value_read_succeeded")
            if isinstance(value.get("application_value_read_succeeded"), bool)
            else None
        ),
        value_good_count=min(max(int(value.get("value_good_count", 0)), 0), 8),
        security_mode=_parse_security_fact(value.get("security_mode")),
        security_policy=_parse_security_fact(value.get("security_policy")),
        truncated=bool(phase.get("truncated", False)),
    )


def _parse_security_fact(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    fact_value = _safe_text(value.get("value"), 256)
    source = value.get("source")
    status = value.get("status")
    if not fact_value or source != "get_endpoints" or status not in {"Good", "Bad"}:
        return {}
    return {"value": fact_value, "source": source, "status": status}


def _safe_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value[:limit] if char.isprintable())


def _safe_optional(
    value: Any, limit: int, allowed: set[str] | None = None, pattern: str | None = None
) -> str | None:
    text = _safe_text(value, limit)
    if not text or (allowed is not None and text not in allowed):
        return None
    if pattern == "hex64" and (
        len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text)
    ):
        return None
    return text
