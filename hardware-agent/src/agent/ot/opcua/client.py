from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import sys
from pathlib import Path
from typing import Any

from .models import (
    OpcUaClientResult,
    OpcUaEndpoint,
    OpcUaRequestStats,
)

MAX_REQUEST_BUDGET = 32
MAX_OPERATION_TIMEOUT_SECONDS = 2.0
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
        )

    async def _invoke(
        self,
        operation: str,
        host: str,
        port: int,
        *,
        request_budget: int,
        timeout: float,
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
            stdout, _ = await asyncio.wait_for(
                process.communicate(request), timeout=timeout_ms / 1000 + 1.0
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            if isinstance(sys.exc_info()[1], asyncio.CancelledError):
                raise
            return OpcUaClientResult("error", error="timeout")

        try:
            response = json.loads(stdout)
            stats = _parse_stats(response)
            if response.get("status") == "ok":
                endpoints = tuple(
                    _parse_endpoint(item) for item in response["endpoints"]
                )
                return OpcUaClientResult("ok", endpoints=endpoints, stats=stats)
            error = response.get("code")
            if error not in _ERRORS:
                error = "service_error"
            return OpcUaClientResult("error", error=error, stats=stats)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return OpcUaClientResult("error", error="invalid_response")


def _helper_command() -> list[str]:
    configured = os.environ.get("DMITRI_OPCUA_BRIDGE")
    if configured:
        return [configured]
    root = Path(__file__).with_name("helper")
    rid = "win-x64" if sys.platform == "win32" else "linux-arm64"
    published = (
        root
        / "publish"
        / rid
        / ("opcua-bridge.exe" if sys.platform == "win32" else "opcua-bridge")
    )
    if published.is_file():
        return [str(published)]
    dll = root / "bin" / "Release" / "net10.0" / "opcua-bridge.dll"
    if not dll.is_file():
        dll = root / "bin" / "Debug" / "net10.0" / "opcua-bridge.dll"
    dotnet = os.environ.get("DOTNET_HOST_PATH", "dotnet")
    if dll.is_file():
        return [dotnet, str(dll)]
    project = root / "opcua-bridge.csproj"
    if project.is_file():
        return [dotnet, "run", "--no-build", "--project", str(project)]
    raise RuntimeError("OPC UA helper is not installed")


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
    )


def _safe_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value[:limit] if char.isprintable())
