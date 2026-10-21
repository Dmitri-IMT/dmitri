from __future__ import annotations

from agent.ot.opcua.client import _parse_mapping


def test_untrusted_node_text_is_capped_and_values_are_discarded() -> None:
    sentinel = "PROCESS_VALUE_SENTINEL"
    result = _parse_mapping(
        {
            "phase": {
                "status": "partial",
                "reason_codes": ["external_reference"],
                "truncated": True,
            },
            "references_observed": 513,
            "value_reads_attempted": 99,
            "nodes": [
                {
                    "node_id": "x" * 500,
                    "depth": 99,
                    "node_class": "Variable",
                    "browse_name": "<img onerror=alert(1)>" * 20,
                    "value": sentinel,
                    "raw_variant": sentinel,
                }
            ],
        }
    )
    assert len(result.nodes[0].node_id) == 256
    assert result.nodes[0].depth == 4
    assert result.references_observed == 512
    assert result.value_reads_attempted == 8
    assert sentinel not in repr(result)
