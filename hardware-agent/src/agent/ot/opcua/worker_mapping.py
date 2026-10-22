from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any

from asyncua import ua

MAX_DEPTH = 4
MAX_NODES = 128
MAX_REFERENCES = 512
MAX_PAGES = 16
PAGE_SIZE = 32
MAX_BROWSE_NEXT = 4
MAX_VALUE_READS = 8
METADATA_BATCH = 14


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value[:limit] if char.isprintable())


def _status(value: Any) -> int:
    return int(getattr(value, "value", 0) or 0)


def _bad(status: Any) -> bool:
    return bool(
        status is not None
        and getattr(status, "is_bad", lambda: bool(_status(status) & 0x80000000))()
    )


async def _release_continuation(client: Any, continuation: bytes) -> bool:
    protocol = getattr(client.uaclient, "protocol", None)
    gate = getattr(getattr(protocol, "adapter", None), "gate", None)
    if gate is None or gate.stats.requests >= gate.ordinary_limit:
        return False
    try:
        released = await client.uaclient.browse_next(
            ua.BrowseNextParameters(
                ReleaseContinuationPoints=True,
                ContinuationPoints=[continuation],
            )
        )
        return len(released) == 1 and not _bad(released[0].StatusCode)
    except Exception:
        return False


def _result(
    status: str,
    reasons: list[str],
    nodes: list[dict[str, Any]],
    refs: list[dict[str, Any]],
    observed: int,
    attempts: int,
    endpoint_index: int,
    endpoint: Any,
    *,
    activated: bool | None = None,
    browsed: bool | None = None,
    truncated: bool = False,
) -> dict[str, Any]:
    variables = [
        n
        for n in nodes
        if n["node_class"] == "Variable"
        and n["node_id"].startswith("ns=")
        and not n["node_id"].startswith("ns=0;")
    ]
    eligible = variables[:MAX_VALUE_READS]
    read_nodes = [n for n in eligible if n.get("value_read_status") is not None]
    app_read = None
    if any(n["value_read_status"] == "Good" for n in read_nodes):
        app_read = True
    elif (
        attempts
        and len(read_nodes) == attempts
        and all(n["value_read_status"] in {"Denied", "Error"} for n in read_nodes)
    ):
        app_read = False
    return {
        "phase": {
            "status": status,
            "reason_codes": list(dict.fromkeys(reasons))[:16],
            "truncated": truncated,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        "nodes": nodes,
        "references": refs[:MAX_REFERENCES],
        "references_observed": observed,
        "value_reads_attempted": attempts,
        "selected_endpoint_index": endpoint_index,
        "anonymous_session_activated": activated,
        "browse_succeeded": browsed,
        "application_value_read_succeeded": app_read,
        "value_good_count": sum(n.get("value_read_status") == "Good" for n in nodes),
        "security_mode": {
            "value": {"None_": "None"}.get(
                getattr(endpoint.SecurityMode, "name", ""),
                getattr(endpoint.SecurityMode, "name", ""),
            ),
            "source": "get_endpoints",
            "status": "Good",
        },
        "security_policy": {
            "value": _text(endpoint.SecurityPolicyUri, 256),
            "source": "get_endpoints",
            "status": "Good",
        },
    }


async def run_mapping(
    client: Any, endpoint: Any, endpoint_index: int, timeout: float
) -> dict[str, Any]:
    """Run the bounded, anonymous metadata map. SDK objects never leave this worker."""
    reasons: list[str] = []
    nodes: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    observed = attempts = 0
    session_open = False
    activated: bool | None = None
    browsed: bool | None = None
    result_holder: list[dict[str, Any]] = []

    def capture_result(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = _result(*args, **kwargs)
        result_holder[:] = [result]
        return result

    app = ua.ApplicationDescription(
        ApplicationUri="urn:dmitri:opcua-scanner",
        ProductUri="urn:dmitri",
        ApplicationName=ua.LocalizedText("Dmitri"),
        ApplicationType=ua.ApplicationType.Client,
    )
    create = ua.CreateSessionParameters(
        ClientDescription=app,
        ServerUri=endpoint.Server.ApplicationUri,
        EndpointUrl=endpoint.EndpointUrl,
        SessionName=os.urandom(12).hex(),
        ClientNonce=os.urandom(32),
        ClientCertificate=b"",
        RequestedSessionTimeout=timeout * 1000,
        MaxResponseMessageSize=131072,
    )
    try:
        await client.uaclient.create_session(create)
        session_open = True
        policy = next(
            (
                p
                for p in endpoint.UserIdentityTokens
                if p.TokenType == ua.UserTokenType.Anonymous
            ),
            None,
        )
        if policy is None:
            return capture_result(
                "denied",
                ["anonymous_denied"],
                nodes,
                refs,
                observed,
                attempts,
                endpoint_index,
                endpoint,
                activated=False,
            )
        token = ua.AnonymousIdentityToken(PolicyId=policy.PolicyId)
        identity = ua.ExtensionObject(
            TypeId=ua.NodeId(
                ua.ObjectIds.AnonymousIdentityToken_Encoding_DefaultBinary
            ),
            Body=ua.ua_binary.struct_to_binary(token),
        )
        activate = ua.ActivateSessionParameters(
            ClientSignature=ua.SignatureData(),
            ClientSoftwareCertificates=[],
            LocaleIds=[],
            UserIdentityToken=identity,
            UserTokenSignature=ua.SignatureData(),
        )
        try:
            await client.uaclient.activate_session(activate)
            activated = True
        except Exception as exc:
            code = _operation_error_reason(client, exc)
            if code == "anonymous_denied":
                return capture_result(
                    "denied",
                    [code],
                    nodes,
                    refs,
                    observed,
                    attempts,
                    endpoint_index,
                    endpoint,
                    activated=False,
                )
            return capture_result(
                "failed",
                [code],
                nodes,
                refs,
                observed,
                attempts,
                endpoint_index,
                endpoint,
                activated=None,
            )

        queue: deque[tuple[ua.NodeId, int]] = deque([(ua.NodeId(85), 0)])
        visited = {"ns=0;i=85"}
        pages = browse_calls = 0
        traversal_stopped = False
        while (
            queue
            and not traversal_stopped
            and len(nodes) < MAX_NODES
            and browse_calls < MAX_NODES
            and observed < MAX_REFERENCES
            and pages < MAX_PAGES
        ):
            current, depth = queue.popleft()
            params = ua.BrowseParameters(
                View=ua.ViewDescription(),
                RequestedMaxReferencesPerNode=PAGE_SIZE,
                NodesToBrowse=[
                    ua.BrowseDescription(
                        NodeId=current,
                        BrowseDirection=ua.BrowseDirection.Forward,
                        ReferenceTypeId=ua.NodeId(33),
                        IncludeSubtypes=True,
                        NodeClassMask=int(ua.NodeClass.Object | ua.NodeClass.Variable),
                        ResultMask=int(
                            ua.BrowseResultMask.NodeClass
                            | ua.BrowseResultMask.BrowseName
                            | ua.BrowseResultMask.DisplayName
                            | ua.BrowseResultMask.TypeDefinition
                        ),
                    )
                ],
            )
            try:
                found = await client.uaclient.browse(params)
            except Exception as exc:
                reason = _operation_error_reason(client, exc)
                reasons.append(reason)
                if reason == "anonymous_denied" and browsed is not True:
                    browsed = False
                break
            pages += 1
            browse_calls += 1
            if len(found) != 1:
                reasons.append("invalid_response")
                if browsed is not True:
                    browsed = None
                break
            page = found[0]
            if _bad(page.StatusCode):
                reason = (
                    "anonymous_denied"
                    if _status(page.StatusCode)
                    == int(ua.StatusCode(ua.StatusCodes.BadUserAccessDenied).value)
                    else "service_error"
                )
                reasons.append(reason)
                if browsed is not True:
                    browsed = False
                break
            browsed = True
            continuation = page.ContinuationPoint
            reference_pages = [page.References]
            seen_points: set[bytes] = set()
            next_count = 0
            while (
                continuation
                and next_count < MAX_BROWSE_NEXT
                and pages < MAX_PAGES
                and len(nodes) < MAX_NODES
                and observed < MAX_REFERENCES
            ):
                point = bytes(continuation)
                if point in seen_points:
                    reasons.append("page_limit")
                    if not await _release_continuation(client, point):
                        traversal_stopped = True
                    continuation = None
                    break
                seen_points.add(point)
                try:
                    more = await client.uaclient.browse_next(
                        ua.BrowseNextParameters(
                            ReleaseContinuationPoints=False,
                            ContinuationPoints=[continuation],
                        )
                    )
                except Exception as exc:
                    reason = _operation_error_reason(client, exc)
                    reasons.append(reason)
                    if browsed is not True:
                        browsed = False if reason == "anonymous_denied" else browsed
                    traversal_stopped = True
                    break
                if len(more) != 1:
                    reasons.append("invalid_response")
                    if browsed is not True:
                        browsed = None
                    traversal_stopped = True
                    break
                pages += 1
                next_count += 1
                page = more[0]
                if _bad(page.StatusCode):
                    reasons.append(
                        "anonymous_denied"
                        if _status(page.StatusCode)
                        == int(ua.StatusCode(ua.StatusCodes.BadUserAccessDenied).value)
                        else "service_error"
                    )
                    if browsed is not True:
                        browsed = False
                    traversal_stopped = True
                    break
                added_references = len(page.References)
                reference_pages.append(page.References)
                next_continuation = page.ContinuationPoint
                if next_continuation and (
                    added_references == 0 or bytes(next_continuation) in seen_points
                ):
                    reasons.append("page_limit")
                    if not await _release_continuation(
                        client, bytes(next_continuation)
                    ):
                        traversal_stopped = True
                    continuation = None
                    break
                continuation = next_continuation
            if continuation:
                reasons.append("page_limit")
                if not await _release_continuation(client, bytes(continuation)):
                    traversal_stopped = True
            # Process each page independently so pagination cannot reorder references.
            for reference_page in reference_pages:
                if len(reference_page) > PAGE_SIZE:
                    reasons.append("decode_limit")
                candidates: list[tuple[Any, ua.NodeId]] = []
                for ref in reference_page[:PAGE_SIZE]:
                    if observed >= MAX_REFERENCES:
                        reasons.append("node_limit")
                        break
                    observed += 1
                    expanded = ref.NodeId
                    if getattr(expanded, "ServerIndex", 0) or getattr(
                        expanded, "NamespaceUri", None
                    ):
                        reasons.append("external_reference")
                        continue
                    try:
                        target = ua.NodeId.from_string(expanded.to_string())
                    except Exception:
                        reasons.append("opaque_node_id_omitted")
                        continue
                    if target.NodeIdType == ua.NodeIdType.ByteString:
                        reasons.append("opaque_node_id_omitted")
                        continue
                    src = _text(current.to_string(), 256)
                    dst = _text(target.to_string(), 256)
                    ref_type_node = ref.ReferenceTypeId
                    ref_type = _text(ref_type_node.to_string(), 256)
                    if (
                        getattr(ref_type_node, "NodeIdType", None)
                        == ua.NodeIdType.ByteString
                    ):
                        reasons.append("opaque_node_id_omitted")
                    elif dst and ref_type:
                        refs.append(
                            {
                                "source_node_id": src,
                                "target_node_id": dst,
                                "reference_type_id": ref_type,
                                "is_forward": bool(ref.IsForward),
                            }
                        )
                    candidates.append((ref, target))
                candidates.sort(
                    key=lambda pair: (
                        0
                        if pair[0].NodeClass == ua.NodeClass.Variable
                        and pair[1].NamespaceIndex > 0
                        else 1 if pair[1].NamespaceIndex > 0 else 2
                    )
                )
                for ref, target in candidates:
                    key = _text(target.to_string(), 256)
                    if not key or key in visited:
                        continue
                    visited.add(key)
                    child_depth = depth + 1
                    if child_depth > MAX_DEPTH:
                        reasons.append("depth_limit")
                        continue
                    if len(nodes) >= MAX_NODES:
                        reasons.append("node_limit")
                        break
                    nodes.append(
                        {
                            "node_id": key,
                            "parent_node_id": _text(current.to_string(), 256),
                            "depth": child_depth,
                            "node_class": ref.NodeClass.name,
                            "browse_name": _text(ref.BrowseName.Name, 128) or None,
                            "display_name": _text(ref.DisplayName.Text, 128) or None,
                            "data_type": None,
                            "value_rank": None,
                            "access_level": None,
                            "user_access_level": None,
                            "value_read_status": None,
                        }
                    )
                    if child_depth < MAX_DEPTH and not traversal_stopped:
                        queue.append((target, child_depth))
            if (
                "anonymous_denied" in reasons
                or "service_error" in reasons
                or "message_size_limit" in reasons
            ):
                break

        if (
            reasons
            and not nodes
            and ("anonymous_denied" in reasons or "service_error" in reasons)
        ):
            return capture_result(
                "denied" if "anonymous_denied" in reasons else "failed",
                reasons,
                nodes,
                refs,
                observed,
                attempts,
                endpoint_index,
                endpoint,
                activated=activated,
                browsed=browsed,
                truncated=True,
            )
        if queue and "node_limit" not in reasons:
            reasons.append("page_limit")
        eligible = [
            node
            for node in nodes
            if node["node_class"] == "Variable"
            and node["node_id"].startswith("ns=")
            and not node["node_id"].startswith("ns=0;")
        ][:MAX_VALUE_READS]
        attributes = [
            ua.AttributeIds.NodeClass,
            ua.AttributeIds.BrowseName,
            ua.AttributeIds.DisplayName,
            ua.AttributeIds.DataType,
            ua.AttributeIds.ValueRank,
            ua.AttributeIds.AccessLevel,
            ua.AttributeIds.UserAccessLevel,
        ]
        if eligible:
            read_ids = [
                ua.ReadValueId(
                    NodeId=ua.NodeId.from_string(node["node_id"]), AttributeId=attribute
                )
                for node in eligible
                for attribute in attributes
            ]
            vals: list[Any] = []
            for offset in range(0, len(read_ids), METADATA_BATCH):
                batch = read_ids[offset : offset + METADATA_BATCH]
                values = await client.uaclient.read(
                    ua.ReadParameters(
                        MaxAge=0,
                        TimestampsToReturn=ua.TimestampsToReturn.Neither,
                        NodesToRead=batch,
                    )
                )
                if len(values) != len(batch):
                    reasons.append("invalid_response")
                    return capture_result(
                        "partial",
                        reasons,
                        nodes,
                        refs,
                        observed,
                        attempts,
                        endpoint_index,
                        endpoint,
                        activated=activated,
                        browsed=browsed,
                        truncated=True,
                    )
                vals.extend(values)
            for idx, node in enumerate(eligible):
                group = vals[idx * 7 : (idx + 1) * 7]
                if any(_bad(item.StatusCode) for item in group):
                    reasons.append("service_error")
                    continue
                datatype = group[3].Value.Value if group[3].Value else None
                if (
                    isinstance(datatype, ua.NodeId)
                    and datatype.NodeIdType == ua.NodeIdType.ByteString
                ):
                    reasons.append("opaque_node_id_omitted")
                else:
                    node["data_type"] = (
                        _text(datatype.to_string(), 256)
                        if isinstance(datatype, ua.NodeId)
                        else None
                    )
                node["value_rank"] = (
                    group[4].Value.Value
                    if group[4].Value and isinstance(group[4].Value.Value, int)
                    else None
                )
                node["access_level"] = (
                    group[5].Value.Value
                    if group[5].Value and isinstance(group[5].Value.Value, int)
                    else None
                )
                node["user_access_level"] = (
                    group[6].Value.Value
                    if group[6].Value and isinstance(group[6].Value.Value, int)
                    else None
                )
                # Drop metadata DataValues and Variant payloads before Value probes.
            vals.clear()
            del vals
            values = None
        else:
            reasons.append("no_eligible_variables")
        if eligible:
            attempts = len(eligible)
            try:
                values = await client.uaclient.read(
                    ua.ReadParameters(
                        MaxAge=0,
                        TimestampsToReturn=ua.TimestampsToReturn.Neither,
                        NodesToRead=[
                            ua.ReadValueId(
                                NodeId=ua.NodeId.from_string(node["node_id"]),
                                AttributeId=ua.AttributeIds.Value,
                            )
                            for node in eligible
                        ],
                    )
                )
                if len(values) != len(eligible):
                    reasons.append("invalid_response")
                    for node in eligible:
                        node["value_read_status"] = "Skipped"
                else:
                    for node, data_value in zip(eligible, values, strict=True):
                        status_value = _status(data_value.StatusCode)
                        node["value_read_status"] = (
                            "Good"
                            if status_value == 0
                            else (
                                "Denied"
                                if status_value
                                == int(
                                    ua.StatusCode(
                                        ua.StatusCodes.BadUserAccessDenied
                                    ).value
                                )
                                else "Error"
                            )
                        )
                        data_value.Value = None
                    values.clear()
                    del values
            except Exception as exc:
                reason = _operation_error_reason(client, exc)
                reasons.append(reason)
                if reason == "anonymous_denied":
                    for node in eligible:
                        node["value_read_status"] = "Denied"
        phase_status = (
            "denied"
            if "anonymous_denied" in reasons and not nodes
            else "completed" if not reasons else "partial"
        )
        return capture_result(
            phase_status,
            reasons,
            nodes,
            refs,
            observed,
            attempts,
            endpoint_index,
            endpoint,
            activated=activated,
            browsed=browsed,
            truncated=bool(reasons),
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        reason = _operation_error_reason(client, exc)
        reasons.append(reason)
        status = (
            "denied"
            if reason == "anonymous_denied" and not nodes
            else "failed" if not nodes else "partial"
        )
        return capture_result(
            status,
            reasons,
            nodes,
            refs,
            observed,
            attempts,
            endpoint_index,
            endpoint,
            activated=activated,
            browsed=browsed,
            truncated=True,
        )
    finally:
        if session_open and not asyncio.current_task().cancelling():
            try:
                async with asyncio.timeout(1.0):
                    await client.uaclient.close_session(False)
            except Exception as exc:
                if result_holder:
                    result = result_holder[0]
                    phase = result["phase"]
                    phase["status"] = "partial"
                    phase["truncated"] = True
                    reason = _exception_reason(exc)
                    reasons = phase.setdefault("reason_codes", [])
                    if reason not in reasons:
                        reasons.append(reason)


def _exception_reason(exc: BaseException) -> str:
    name = type(exc).__name__
    if name in {"TimeoutError", "TimeoutException"}:
        return "timeout"
    status = getattr(exc, "code", None)
    if status is None:
        args = getattr(exc, "args", ())
        first = args[0] if args else None
        status = getattr(first, "value", None)
    if status in {
        int(ua.StatusCodes.BadUserAccessDenied),
        int(ua.StatusCodes.BadIdentityTokenRejected),
        int(ua.StatusCodes.BadIdentityTokenInvalid),
    }:
        return "anonymous_denied"
    if status == int(ua.StatusCodes.BadTooManyOperations):
        return "request_budget_exhausted"
    if status in {
        int(ua.StatusCodes.BadEncodingLimitsExceeded),
        int(ua.StatusCodes.BadResponseTooLarge),
    }:
        return "message_size_limit"
    if status == int(ua.StatusCodes.BadRequestTimeout):
        return "timeout"
    if name == "ProtocolViolation":
        return (
            str(exc)
            if str(exc)
            in {
                "timeout",
                "request_budget_exhausted",
                "message_size_limit",
                "service_not_allowed",
            }
            else "service_error"
        )
    return "service_error"


def _operation_error_reason(client: Any, exc: BaseException) -> str:
    protocol = getattr(client.uaclient, "protocol", None)
    gate = getattr(getattr(protocol, "adapter", None), "gate", None)
    if gate is not None and gate.stats.requests >= gate.ordinary_limit:
        return "request_budget_exhausted"
    return _exception_reason(exc)
