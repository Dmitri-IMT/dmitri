from __future__ import annotations

from datetime import datetime, timezone

from .client import OpcUaClient
from .models import OpcUaEndpoint, OpcUaMappingResult

MAX_DEPTH = 4
MAX_NODES = 128
MAX_REFERENCES = 512
MAX_PAGES = 16
MAX_PAGE_SIZE = 32
MAX_BROWSE_NEXT_PER_NODE = 4
MAX_VALUE_READS = 8


async def map_opcua_service(
    client: OpcUaClient,
    host: str,
    port: int,
    endpoints: tuple[OpcUaEndpoint, ...],
    *,
    request_budget: int = 32,
    timeout: float = 2.0,
) -> OpcUaMappingResult:
    """Run one anonymous mapping session; process Values stay in the helper."""
    endpoint = next(
        (
            item
            for item in endpoints
            if item.security_policy_uri
            == "http://opcfoundation.org/UA/SecurityPolicy#None"
            and item.security_mode == "None"
            and "Anonymous" in item.user_token_types
        ),
        None,
    )
    now = datetime.now(timezone.utc)
    if endpoint is None:
        return OpcUaMappingResult(
            "unsupported_security",
            ("security_configuration_required",),
            observed_at=now,
        )
    result = await client.map_anonymous(
        host,
        port,
        endpoint,
        request_budget=request_budget,
        timeout=timeout,
    )
    if result.mapping is not None:
        return result.mapping
    reason = {
        "timeout": "timeout",
        "request_budget_exhausted": "request_budget_exhausted",
        "service_not_allowed": "service_not_allowed",
        "invalid_response": "invalid_response",
        "message_size_limit": "message_size_limit",
        "unsupported_operation": "security_configuration_required",
    }.get(result.error, "service_error")
    status = (
        "timed_out"
        if reason == "timeout"
        else "denied"
        if reason == "anonymous_denied"
        else "failed"
    )
    return OpcUaMappingResult(status, (reason,), observed_at=now)
