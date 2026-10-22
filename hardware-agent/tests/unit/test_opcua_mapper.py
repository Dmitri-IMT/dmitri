from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from agent.ot.opcua.mapper import (
    MAX_BROWSE_NEXT_PER_NODE,
    MAX_NODES,
    MAX_PAGES,
    map_opcua_service,
)
from agent.ot.opcua.models import OpcUaEndpoint


def test_mapping_refuses_endpoints_without_explicit_anonymous_none() -> None:
    result = asyncio.run(map_opcua_service(None, "192.0.2.4", 4840, ()))  # type: ignore[arg-type]
    assert result.status == "unsupported_security"
    assert result.reason_codes == ("security_configuration_required",)
    assert result.nodes == ()


def test_empty_timeout_is_classified_without_indexing_exception_args() -> None:
    from agent.ot.opcua.worker_mapping import _exception_reason

    assert _exception_reason(TimeoutError()) == "timeout"


@pytest.mark.parametrize(
    ("statuses", "attempts", "expected"),
    [
        (["Good", "Skipped"], 2, True),
        (["Denied", "Error"], 2, False),
        (["Denied", "Skipped"], 2, None),
        (["Skipped"], 1, None),
        (["Error"], 1, False),
        (["Good"], 1, True),
    ],
)
def test_value_read_summary_only_reports_proven_results(
    statuses: list[str], attempts: int, expected: bool | None
) -> None:
    from agent.ot.opcua.worker_mapping import _result
    from asyncua import ua

    endpoint = SimpleNamespace(
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    nodes = [
        {
            "node_id": f"ns=2;i={index + 1}",
            "node_class": "Variable",
            "value_read_status": status,
        }
        for index, status in enumerate(statuses)
    ]

    result = _result("partial", ["timeout"], nodes, [], 0, attempts, 0, endpoint)

    assert result["application_value_read_succeeded"] is expected
    assert result["value_good_count"] == statuses.count("Good")


@pytest.mark.asyncio
async def test_activation_timeout_leaves_session_and_browse_facts_unknown() -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    class UaClient:
        async def create_session(self, _params):
            return None

        async def activate_session(self, _params):
            raise TimeoutError()

        async def close_session(self, _delete_subscriptions):
            return None

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[
            ua.UserTokenPolicy(
                PolicyId="anonymous", TokenType=ua.UserTokenType.Anonymous
            )
        ],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    assert result["anonymous_session_activated"] is None
    assert result["browse_succeeded"] is None
    assert result["phase"]["reason_codes"] == ["timeout"]


@pytest.mark.asyncio
async def test_metadata_timeout_preserves_successful_browse_fact_and_nodes() -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    class UaClient:
        async def create_session(self, _params):
            return None

        async def activate_session(self, _params):
            return None

        async def browse(self, params):
            if params.NodesToBrowse[0].NodeId.Identifier == 85:
                variable = _browse_reference(1, "Variable")
                variable.NodeClass = ua.NodeClass.Variable
                return [ua.BrowseResult(References=[variable])]
            return [ua.BrowseResult()]

        async def read(self, _params):
            raise TimeoutError()

        async def close_session(self, _delete_subscriptions):
            return None

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[
            ua.UserTokenPolicy(
                PolicyId="anonymous", TokenType=ua.UserTokenType.Anonymous
            )
        ],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    assert result["anonymous_session_activated"] is True
    assert result["browse_succeeded"] is True
    assert result["nodes"][0]["browse_name"] == "Variable"
    assert result["phase"]["status"] == "partial"
    assert result["phase"]["reason_codes"] == ["timeout"]
    assert result["application_value_read_succeeded"] is None


def _browse_reference(identifier: int, name: str):
    from asyncua import ua

    return ua.ReferenceDescription(
        ReferenceTypeId=ua.NodeId(33),
        IsForward=True,
        NodeId=ua.ExpandedNodeId(identifier, NamespaceIndex=2),
        BrowseName=ua.QualifiedName(name),
        DisplayName=ua.LocalizedText(name),
        NodeClass=ua.NodeClass.Object,
    )


@pytest.mark.asyncio
async def test_repeated_continuation_is_released_before_bfs_continues() -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    events: list[tuple[str, int | bool]] = []

    class UaClient:
        def __init__(self):
            self.protocol = SimpleNamespace(
                adapter=SimpleNamespace(
                    gate=SimpleNamespace(
                        stats=SimpleNamespace(requests=1), ordinary_limit=16
                    )
                )
            )
            self.root_browse_count = 0
            self.next_count = 0

        async def create_session(self, _params):
            return None

        async def activate_session(self, _params):
            return None

        async def browse(self, params):
            node = params.NodesToBrowse[0].NodeId
            events.append(("browse", node.Identifier))
            if node.Identifier == 85:
                self.root_browse_count += 1
                return [
                    ua.BrowseResult(
                        ContinuationPoint=b"first",
                        References=[_browse_reference(1, "One")],
                    )
                ]
            return [ua.BrowseResult()]

        async def browse_next(self, params):
            events.append(("next", params.ReleaseContinuationPoints))
            if params.ReleaseContinuationPoints:
                return [ua.BrowseResult()]
            self.next_count += 1
            if self.next_count == 1:
                return [
                    ua.BrowseResult(
                        ContinuationPoint=b"second",
                        References=[_browse_reference(2, "Two")],
                    )
                ]
            return [
                ua.BrowseResult(
                    ContinuationPoint=b"second",
                    References=[],
                )
            ]

        async def close_session(self, _delete_subscriptions):
            return None

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[
            ua.UserTokenPolicy(
                PolicyId="anonymous", TokenType=ua.UserTokenType.Anonymous
            )
        ],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    release_index = events.index(("next", True))
    first_child_browse = events.index(("browse", 1))
    assert release_index < first_child_browse
    assert [node["browse_name"] for node in result["nodes"]] == ["One", "Two"]
    assert result["phase"]["reason_codes"].count("page_limit") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("next_failure", ["bad_status", "empty_response"])
async def test_browse_succeeded_remains_true_after_bad_browse_next(
    next_failure: str,
) -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    class UaClient:
        def __init__(self):
            self.protocol = SimpleNamespace(
                adapter=SimpleNamespace(
                    gate=SimpleNamespace(
                        stats=SimpleNamespace(requests=1), ordinary_limit=16
                    )
                )
            )
            self.calls = 0

        async def create_session(self, _params):
            return None

        async def activate_session(self, _params):
            return None

        async def browse(self, _params):
            return [
                ua.BrowseResult(
                    ContinuationPoint=b"cursor",
                    References=[_browse_reference(1, "One")],
                )
            ]

        async def browse_next(self, params):
            if params.ReleaseContinuationPoints:
                return [ua.BrowseResult()]
            self.calls += 1
            if next_failure == "empty_response":
                return []
            return [
                ua.BrowseResult(
                    StatusCode=ua.StatusCode(ua.StatusCodes.BadUserAccessDenied)
                )
            ]

        async def close_session(self, _delete_subscriptions):
            return None

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[
            ua.UserTokenPolicy(
                PolicyId="anonymous", TokenType=ua.UserTokenType.Anonymous
            )
        ],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    assert result["browse_succeeded"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "release_failure", ["negative_status", "ambiguous_next", "no_budget"]
)
async def test_unreleased_continuation_stops_bfs(
    release_failure: str,
) -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    events: list[tuple[str, bool | int]] = []

    class UaClient:
        def __init__(self):
            requests = 16 if release_failure == "no_budget" else 1
            self.gate = SimpleNamespace(
                stats=SimpleNamespace(requests=requests), ordinary_limit=16
            )
            self.protocol = SimpleNamespace(adapter=SimpleNamespace(gate=self.gate))

        async def create_session(self, _params):
            return None

        async def activate_session(self, _params):
            return None

        async def browse(self, params):
            node = params.NodesToBrowse[0].NodeId
            events.append(("browse", node.Identifier))
            if node.Identifier == 85:
                return [
                    ua.BrowseResult(
                        ContinuationPoint=b"cursor",
                        References=[_browse_reference(1, "One")],
                    )
                ]
            return [ua.BrowseResult()]

        async def browse_next(self, params):
            events.append(("next", params.ReleaseContinuationPoints))
            if self.gate.stats.requests >= self.gate.ordinary_limit:
                raise RuntimeError("ordinary budget exhausted")
            self.gate.stats.requests += 1
            if (
                not params.ReleaseContinuationPoints
                and release_failure == "ambiguous_next"
            ):
                raise ConnectionError()
            if release_failure == "negative_status":
                return [
                    ua.BrowseResult(
                        StatusCode=ua.StatusCode(ua.StatusCodes.BadUserAccessDenied)
                    )
                ]
            return [ua.BrowseResult()]

        async def close_session(self, _delete_subscriptions):
            return None

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[
            ua.UserTokenPolicy(
                PolicyId="anonymous", TokenType=ua.UserTokenType.Anonymous
            )
        ],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    assert ("browse", 1) not in events
    if release_failure == "no_budget":
        assert ("next", True) not in events
    else:
        assert events[-1] == ("next", True)
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["browse_name"] == "One"
    assert "page_limit" in result["phase"]["reason_codes"]
    assert result["browse_succeeded"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_error", [TimeoutError(), ConnectionError()])
async def test_close_session_failure_preserves_partial_nodes_and_reasons(
    cleanup_error: BaseException,
) -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    browse_count = 0

    class UaClient:
        async def create_session(self, _params):
            return None

        async def activate_session(self, _params):
            return None

        async def browse(self, _params):
            nonlocal browse_count
            browse_count += 1
            if browse_count == 1:
                external = ua.ReferenceDescription(
                    ReferenceTypeId=ua.NodeId(33),
                    IsForward=True,
                    NodeId=ua.ExpandedNodeId(99, NamespaceIndex=2, ServerIndex=1),
                    BrowseName=ua.QualifiedName("External"),
                    DisplayName=ua.LocalizedText("External"),
                    NodeClass=ua.NodeClass.Object,
                )
                return [
                    ua.BrowseResult(References=[_browse_reference(1, "One"), external])
                ]
            return [ua.BrowseResult()]

        async def close_session(self, _delete_subscriptions):
            raise cleanup_error

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[
            ua.UserTokenPolicy(
                PolicyId="anonymous", TokenType=ua.UserTokenType.Anonymous
            )
        ],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    assert result["phase"]["status"] == "partial"
    assert {
        "external_reference",
        "timeout" if isinstance(cleanup_error, TimeoutError) else "service_error",
    } <= set(result["phase"]["reason_codes"])
    assert result["nodes"]
    assert result["browse_succeeded"] is True


@pytest.mark.asyncio
async def test_create_session_timeout_leaves_activation_unknown() -> None:
    from agent.ot.opcua.worker_mapping import run_mapping
    from asyncua import ua

    class UaClient:
        async def create_session(self, _params):
            raise TimeoutError()

    endpoint = SimpleNamespace(
        Server=SimpleNamespace(ApplicationUri="urn:test"),
        EndpointUrl="opc.tcp://127.0.0.1:4840/",
        UserIdentityTokens=[],
        SecurityMode=ua.MessageSecurityMode.None_,
        SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#None",
    )
    result = await run_mapping(SimpleNamespace(uaclient=UaClient()), endpoint, 0, 1.0)

    assert result["anonymous_session_activated"] is None
    assert result["phase"]["reason_codes"] == ["timeout"]


def test_mapping_client_result_contains_only_categories_and_bounded_metadata() -> None:
    endpoint = OpcUaEndpoint(
        endpoint_url="opc.tcp://192.0.2.4:4840/",
        security_policy_uri="http://opcfoundation.org/UA/SecurityPolicy#None",
        security_mode="None",
        transport_profile_uri="ua-tcp",
        security_level=0,
        user_token_count=1,
        user_token_types=("Anonymous",),
    )

    class Client:
        async def map_anonymous(self, *_args, **_kwargs):
            from agent.ot.opcua.client import _parse_mapping
            from agent.ot.opcua.models import OpcUaClientResult

            return OpcUaClientResult(
                "ok",
                mapping=_parse_mapping(
                    {
                        "phase": {
                            "status": "completed",
                            "reason_codes": [],
                            "truncated": False,
                        },
                        "references_observed": 1,
                        "value_reads_attempted": 1,
                        "nodes": [
                            {
                                "node_id": "ns=2;i=3",
                                "depth": 1,
                                "node_class": "Variable",
                                "browse_name": "<script>bad</script>",
                                "value_read_status": "Good",
                                "value": "PROCESS_VALUE_SENTINEL",
                            }
                        ],
                    }
                ),
            )

    result = asyncio.run(map_opcua_service(Client(), "192.0.2.4", 4840, (endpoint,)))  # type: ignore[arg-type]
    assert result.nodes[0].browse_name == "<script>bad</script>"
    assert "PROCESS_VALUE_SENTINEL" not in repr(result)


def test_mapping_error_preserves_transport_count_and_separate_deadline() -> None:
    from agent.ot.opcua.models import OpcUaClientResult, OpcUaRequestStats

    endpoint = OpcUaEndpoint(
        endpoint_url="opc.tcp://192.0.2.4:4840/",
        security_policy_uri="http://opcfoundation.org/UA/SecurityPolicy#None",
        security_mode="None",
        transport_profile_uri="ua-tcp",
        security_level=0,
        user_token_count=1,
        user_token_types=("Anonymous",),
    )
    seen = {}

    class Client:
        async def map_anonymous(self, *_args, **kwargs):
            seen.update(kwargs)
            return OpcUaClientResult(
                "error",
                error="timeout",
                stats=OpcUaRequestStats(requests_total=3),
            )

    result = asyncio.run(
        map_opcua_service(
            Client(), "192.0.2.4", 4840, (endpoint,), timeout=2.0, deadline=17.0
        )
    )
    assert result.status == "timed_out"
    assert result.requests_sent == 3
    assert seen["timeout"] == 2.0
    assert seen["deadline"] == 17.0


def test_transport_parser_retains_measured_write_attempt_counter() -> None:
    from agent.ot.opcua.client import _parse_stats

    stats = _parse_stats({"requests_total": 4, "write_requests_sent": 1})
    assert stats.requests_total == 4
    assert stats.write_requests_sent == 1


def test_mapping_parser_accepts_architecture_high_water_limits() -> None:
    from agent.ot.opcua.client import _parse_mapping

    result = _parse_mapping(
        {
            "phase": {
                "status": "partial",
                "reason_codes": ["page_limit", "node_limit"],
                "truncated": True,
            },
            "nodes": [
                {
                    "node_id": f"ns=2;i={node_index + 1}",
                    "depth": 4,
                    "node_class": "Object",
                }
                for node_index in range(128)
            ],
            "references_observed": 512,
            "value_reads_attempted": 8,
        }
    )

    assert (MAX_NODES, MAX_PAGES, MAX_BROWSE_NEXT_PER_NODE) == (128, 16, 4)
    assert len(result.nodes) == 128
    assert result.references_observed == 512
    assert result.status == "partial"
    assert result.truncated is True


def test_mapping_parser_preserves_bounded_reference_edges() -> None:
    from agent.ot.opcua.client import _parse_mapping

    result = _parse_mapping(
        {
            "phase": {"status": "partial", "reason_codes": ["node_limit"]},
            "nodes": [],
            "references": [
                {
                    "source_node_id": "ns=0;i=85",
                    "target_node_id": "ns=2;i=3",
                    "reference_type_id": "ns=0;i=35",
                    "is_forward": True,
                }
            ],
            "references_observed": 1,
        }
    )

    assert len(result.references) == 1
    assert result.references[0].source_node_id == "ns=0;i=85"
    assert result.references[0].target_node_id == "ns=2;i=3"
    assert result.references[0].is_forward is True


def test_mapping_parser_rejects_helper_node_count_above_ipc_limit() -> None:
    from agent.ot.opcua.client import _parse_mapping

    with pytest.raises(TypeError, match="invalid mapping nodes"):
        _parse_mapping(
            {
                "phase": {"status": "partial"},
                "nodes": [
                    {"node_id": f"ns=2;i={index}", "depth": 1, "node_class": "Object"}
                    for index in range(129)
                ],
            }
        )


def test_mapping_parser_preserves_cycle_reference_edges() -> None:
    from agent.ot.opcua.client import _parse_mapping

    result = _parse_mapping(
        {
            "phase": {"status": "partial"},
            "nodes": [],
            "references": [
                {
                    "source_node_id": "ns=2;i=1",
                    "target_node_id": "ns=2;i=2",
                    "reference_type_id": "ns=0;i=35",
                    "is_forward": True,
                },
                {
                    "source_node_id": "ns=2;i=2",
                    "target_node_id": "ns=2;i=1",
                    "reference_type_id": "ns=0;i=35",
                    "is_forward": True,
                },
            ],
        }
    )

    assert [
        (edge.source_node_id, edge.target_node_id) for edge in result.references
    ] == [
        ("ns=2;i=1", "ns=2;i=2"),
        ("ns=2;i=2", "ns=2;i=1"),
    ]
