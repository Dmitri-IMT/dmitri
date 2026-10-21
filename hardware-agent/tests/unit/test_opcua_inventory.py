from dataclasses import replace
from datetime import datetime, timezone

from agent.ot.opcua.client import _parse_endpoint
from agent.ot.opcua.inventory import (
    inventory_from_result,
    sanitize_certificate_fingerprint,
    sanitize_endpoint_url,
    sanitize_identity,
)
from agent.ot.opcua.models import OpcUaClientResult, OpcUaEndpoint


def _endpoint(url: str) -> OpcUaEndpoint:
    return OpcUaEndpoint(
        endpoint_url=url,
        security_policy_uri="http://opcfoundation.org/UA/SecurityPolicy#None",
        security_mode="None",
        transport_profile_uri="http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary",
        security_level=0,
        user_token_count=1,
    )


def test_valid_empty_get_endpoints_confirms_protocol_without_finding() -> None:
    inventory = inventory_from_result(
        "192.0.2.10",
        4840,
        OpcUaClientResult("ok"),
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert inventory.confidence == "confirmed"
    assert inventory.inventory_status == "completed"
    assert inventory.endpoints == ()
    assert inventory.identity == {
        "application_uri": None,
        "product_uri": None,
        "application_name": None,
        "application_type": None,
    }
    assert inventory.certificate_sha256 is None
    assert not hasattr(inventory, "findings")


def test_inventory_keeps_only_semantic_endpoints_for_discovered_target() -> None:
    result = OpcUaClientResult(
        "ok",
        endpoints=(
            _endpoint("opc.tcp://192.0.2.10:4840/valid"),
            _endpoint("opc.tcp://192.0.2.11:4840/other-host"),
            _endpoint("opc.tcp://user:secret@192.0.2.10:4840/secret"),
            _endpoint("http://192.0.2.10:4840/not-ua"),
        ),
    )
    inventory = inventory_from_result("192.0.2.10", 4840, result)
    assert inventory.confidence == "confirmed"
    assert [item.endpoint_url for item in inventory.endpoints] == [
        "opc.tcp://192.0.2.10:4840/valid"
    ]
    assert "secret" not in repr(inventory)


def test_inventory_preserves_bounded_announced_metadata_and_token_types() -> None:
    endpoint = _endpoint("opc.tcp://192.0.2.10:4840/")
    endpoint = replace(
        endpoint,
        user_token_types=("Anonymous", "UserName"),
        application_uri="urn:example:server",
        product_uri="urn:example:product",
        application_name="Controller",
        application_type="Server",
        certificate_sha256="a" * 64,
    )
    inventory = inventory_from_result(
        "192.0.2.10", 4840, OpcUaClientResult("ok", endpoints=(endpoint,))
    )
    assert inventory.identity == {
        "application_uri": "urn:example:server",
        "product_uri": "urn:example:product",
        "application_name": "Controller",
        "application_type": "Server",
    }
    assert inventory.application_type == "Server"
    assert inventory.certificate_sha256 == "a" * 64
    assert inventory.endpoints[0].user_token_types == ("Anonymous", "UserName")
    assert inventory.reason_codes == ()
    assert not inventory.truncated


def test_ipc_endpoint_parser_limits_announcements_and_drops_unknown_tokens() -> None:
    endpoint = _parse_endpoint(
        {
            "endpoint_url": "opc.tcp://192.0.2.10:4840/",
            "security_policy": "None",
            "security_mode": "None",
            "transport_profile": "ua-tcp",
            "security_level": 0,
            "user_token_count": 7,
            "user_token_types": ["Anonymous", "SecretToken", "UserName"],
            "application_uri": "u" * 200,
            "product_uri": "urn:example:product",
            "application_name": "\x00Controller",
            "application_type": "Server",
            "certificate_sha256": "A" * 64,
        }
    )
    assert endpoint.user_token_count == 7
    assert endpoint.user_token_types == ("Anonymous", "UserName")
    assert endpoint.application_uri == "u" * 128
    assert endpoint.application_name == "Controller"
    assert endpoint.certificate_sha256 is None


def test_inventory_caps_endpoint_count_and_keeps_identity_and_certificate_null() -> (
    None
):
    inventory = inventory_from_result(
        "192.0.2.10",
        4840,
        OpcUaClientResult(
            "ok",
            endpoints=tuple(
                _endpoint(f"opc.tcp://192.0.2.10:4840/{index}") for index in range(17)
            ),
        ),
    )
    assert len(inventory.endpoints) == 16
    assert inventory.inventory_status == "partial"
    assert inventory.reason_code == "endpoint_limit"
    assert inventory.identity == {
        "application_uri": None,
        "product_uri": None,
        "application_name": None,
        "application_type": None,
    }
    assert inventory.certificate_sha256 is None


def test_non_ua_response_does_not_confirm_and_failure_reason_is_closed() -> None:
    inventory = inventory_from_result(
        "192.0.2.10", 4840, OpcUaClientResult("error", error="timeout")
    )
    assert inventory.confidence == "suspected"
    assert inventory.inventory_status == "timed_out"
    assert inventory.reason_code == "timeout"


def test_nonempty_response_with_only_malformed_endpoints_stays_suspected() -> None:
    inventory = inventory_from_result(
        "192.0.2.10",
        4840,
        OpcUaClientResult("ok", endpoints=(_endpoint("opc.tcp://192.0.2.11:4840/"),)),
    )
    assert inventory.confidence == "suspected"
    assert inventory.inventory_status == "partial"
    assert inventory.reason_code == "endpoint_target_mismatch"


def test_semantically_invalid_get_endpoints_description_does_not_confirm() -> None:
    for endpoint in (
        OpcUaEndpoint(
            endpoint_url="opc.tcp://192.0.2.10:4840/",
            security_policy_uri="not-a-ua-policy",
            security_mode="None",
            transport_profile_uri="http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary",
            security_level=0,
            user_token_count=1,
        ),
        OpcUaEndpoint(
            endpoint_url="opc.tcp://192.0.2.10:4840/",
            security_policy_uri="http://opcfoundation.org/UA/SecurityPolicy#None",
            security_mode="None",
            transport_profile_uri="http://example.invalid/transport#UABinary",
            security_level=0,
            user_token_count=1,
        ),
    ):
        inventory = inventory_from_result(
            "192.0.2.10", 4840, OpcUaClientResult("ok", endpoints=(endpoint,))
        )
        assert inventory.confidence == "suspected"
        assert inventory.endpoints == ()


def test_endpoint_truncation_marker_marks_inventory_partial_at_exact_cap() -> None:
    result = OpcUaClientResult(
        "ok",
        endpoints=tuple(
            _endpoint(f"opc.tcp://192.0.2.10:4840/{index}") for index in range(16)
        ),
        endpoints_truncated=True,
    )
    inventory = inventory_from_result("192.0.2.10", 4840, result)
    assert len(inventory.endpoints) == 16
    assert inventory.inventory_status == "partial"
    assert inventory.reason_code == "endpoint_limit"


def test_url_identity_and_certificate_sanitizers_bound_untrusted_text() -> None:
    assert sanitize_endpoint_url("opc.tcp://192.0.2.10:4840/x", "192.0.2.10", 4840)
    for url in (
        "opc.tcp://192.0.2.11:4840/x",
        "opc.tcp://192.0.2.10:4841/x",
        "opc.tcp://user:pw@192.0.2.10:4840/x",
        "opc.tcp://192.0.2.10:4840/x?secret=1",
        "opc.tcp://name.local:4840/x",
    ):
        assert sanitize_endpoint_url(url, "192.0.2.10", 4840) is None
    assert sanitize_identity("<b>PLC</b>\n") == "<b>PLC</b>"
    assert sanitize_identity("x" * 300) == "x" * 128
    assert sanitize_certificate_fingerprint("a" * 64) == "a" * 64
    assert sanitize_certificate_fingerprint("subject=private") is None
