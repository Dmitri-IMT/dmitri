from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .client import OpcUaClient
from .models import OpcUaClientResult, OpcUaInventory, OpcUaInventoryEndpoint

MAX_ENDPOINTS = 16
MAX_TEXT = 128
MAX_URL = 256
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UA_TCP_BINARY_PROFILE = (
    "http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary"
)
_SECURITY_POLICIES = {
    f"http://opcfoundation.org/UA/SecurityPolicy#{name}"
    for name in (
        "None",
        "Basic128Rsa15",
        "Basic256",
        "Basic256Sha256",
        "Aes128_Sha256_RsaOaep",
        "Aes256_Sha256_RsaPss",
    )
}


async def inventory_opcua_service(
    client: OpcUaClient,
    host: str,
    port: int,
    *,
    request_budget: int = 32,
    timeout: float = 2.0,
    pacing_ms: int = 100,
) -> OpcUaInventory:
    """Inspect a discovered IPv4 TCP service; announcements are observations only."""
    ip = ipaddress.IPv4Address(host)
    if not 1 <= port <= 65535:
        raise ValueError("invalid OPC UA port")
    observed_at = datetime.now(timezone.utc)
    result = await client.discover_endpoints(
        str(ip),
        port,
        request_budget=request_budget,
        timeout=timeout,
        pacing_ms=pacing_ms,
    )
    return inventory_from_result(str(ip), port, result, observed_at=observed_at)


def inventory_from_result(
    host: str,
    port: int,
    result: OpcUaClientResult,
    *,
    observed_at: datetime | None = None,
) -> OpcUaInventory:
    """Validate and minimize a bounded client response before it enters scan output."""
    ip = ipaddress.IPv4Address(host)
    if not 1 <= port <= 65535:
        raise ValueError("invalid OPC UA port")
    when = observed_at or datetime.now(timezone.utc)
    if result.status != "ok":
        status = "timed_out" if result.error == "timeout" else "failed"
        reason = "timeout" if result.error == "timeout" else "endpoint_discovery_failed"
        return OpcUaInventory(
            "opcua_tcp",
            port,
            "suspected",
            ("tcp_candidate",),
            status,
            when,
            reason_code=reason,
            reason_codes=(reason,),
            client_endpoints=(),
            requests_sent=result.stats.requests_total,
            request_count_known=result.request_count_known,
            write_requests_sent=result.stats.write_requests_sent,
        )

    endpoints: list[OpcUaInventoryEndpoint] = []
    rejected_endpoint_count = 0
    for endpoint in result.endpoints[:MAX_ENDPOINTS]:
        sanitized = sanitize_endpoint_url(endpoint.endpoint_url, str(ip), port)
        if sanitized is None:
            rejected_endpoint_count += 1
            continue
        policy = _safe_text(endpoint.security_policy_uri, MAX_URL)
        mode = (
            endpoint.security_mode
            if endpoint.security_mode in {"None", "Sign", "SignAndEncrypt"}
            else ""
        )
        profile = _safe_text(endpoint.transport_profile_uri, MAX_URL)
        # A valid endpoint description needs a URL, policy, mode and UA TCP profile.
        if not (
            policy in _SECURITY_POLICIES and mode and profile == _UA_TCP_BINARY_PROFILE
        ):
            rejected_endpoint_count += 1
            continue
        endpoints.append(
            OpcUaInventoryEndpoint(
                endpoint_url=sanitized,
                security_policy_uri=policy,
                security_mode=mode,
                transport_profile_uri=profile,
                security_level=min(max(int(endpoint.security_level), 0), 255),
                user_token_count=min(max(int(endpoint.user_token_count), 0), 8),
                target_matches=True,
                user_token_types=tuple(endpoint.user_token_types[:8]),
            )
        )
    # An empty valid response confirms UA; malformed non-empty descriptions do not.
    invalid_only_response = bool(result.endpoints) and not endpoints
    truncated = result.endpoints_truncated or len(result.endpoints) > MAX_ENDPOINTS
    partial = rejected_endpoint_count > 0 or truncated
    return OpcUaInventory(
        "opcua_tcp",
        port,
        "suspected" if invalid_only_response else "confirmed",
        ("opcua_get_endpoints",),
        "partial" if partial else "completed",
        when,
        endpoints=tuple(endpoints),
        identity={
            "application_uri": (
                sanitize_identity(result.endpoints[0].application_uri)
                if result.endpoints
                else None
            ),
            "product_uri": (
                sanitize_identity(result.endpoints[0].product_uri)
                if result.endpoints
                else None
            ),
            "application_name": (
                sanitize_identity(result.endpoints[0].application_name)
                if result.endpoints
                else None
            ),
            "application_type": (
                result.endpoints[0].application_type
                if result.endpoints
                and result.endpoints[0].application_type
                in {"Server", "Client", "ClientAndServer", "DiscoveryServer"}
                else None
            ),
        },
        application_type=(
            result.endpoints[0].application_type
            if result.endpoints
            and result.endpoints[0].application_type
            in {"Server", "Client", "ClientAndServer", "DiscoveryServer"}
            else None
        ),
        certificate_sha256=(
            sanitize_certificate_fingerprint(result.endpoints[0].certificate_sha256)
            if result.endpoints
            else None
        ),
        reason_code=(
            "endpoint_limit"
            if truncated
            else "endpoint_target_mismatch" if rejected_endpoint_count else None
        ),
        reason_codes=(
            ("endpoint_limit",)
            if truncated
            else ("endpoint_target_mismatch",) if rejected_endpoint_count else ()
        ),
        truncated=truncated,
        client_endpoints=result.endpoints,
        requests_sent=result.stats.requests_total,
        write_requests_sent=result.stats.write_requests_sent,
    )


def sanitize_endpoint_url(
    value: str, discovered_ip: str, discovered_port: int
) -> str | None:
    if (
        not isinstance(value, str)
        or len(value) > MAX_URL
        or any(not c.isprintable() for c in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        ip = ipaddress.ip_address(parsed.hostname or "")
        actual_port = parsed.port
    except (ValueError, TypeError):
        return None
    if (
        parsed.scheme.lower() != "opc.tcp"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not isinstance(ip, ipaddress.IPv4Address)
        or ip != ipaddress.IPv4Address(discovered_ip)
        or actual_port != discovered_port
        or not parsed.path.startswith("/")
    ):
        return None
    path = parsed.path[:MAX_URL]
    return f"opc.tcp://{ip}:{actual_port}{path}"


def sanitize_identity(value: object) -> str | None:
    return _safe_text(value, MAX_TEXT) or None


def sanitize_certificate_fingerprint(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.lower().removeprefix("sha256:")
    return normalized if _SHA256.fullmatch(normalized) else None


def _safe_text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value[:limit] if ch.isprintable())
