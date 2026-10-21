from __future__ import annotations

import asyncio

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
