from __future__ import annotations

import json

import pytest
from agent.ot.policy import (
    MappingProfile,
    MappingRangeRule,
    OtAutomationPolicy,
    OtPolicyError,
    load_ot_policy,
)
from pydantic import ValidationError


def test_missing_policy_uses_bounded_defaults(tmp_path) -> None:
    policy = load_ot_policy(tmp_path / "missing.json")

    assert policy.version == 1
    assert policy.max_mapping_requests_per_host == 32
    assert policy.inter_request_delay_ms == 100
    assert policy.mapping_profiles == []


def test_policy_rejects_ranges_and_unit_ids_outside_product_limits() -> None:
    with pytest.raises(ValidationError):
        MappingRangeRule(
            address_space="holding_register",
            start_address=65530,
            count=16,
        )

    with pytest.raises(ValidationError):
        MappingProfile(
            name="invalid",
            selector={"cidrs": ["192.168.1.0/24"]},
            unit_ids=[0],
            ranges=[{"address_space": "coil", "start_address": 0, "count": 1}],
        )


def test_invalid_policy_file_fails_closed(tmp_path) -> None:
    path = tmp_path / "ot-policy.json"
    path.write_text(json.dumps({"max_mapping_requests_per_host": 99}))

    with pytest.raises(OtPolicyError, match="Invalid OT automation policy"):
        load_ot_policy(path)


def test_local_policy_cannot_remove_minimum_inter_request_delay() -> None:
    with pytest.raises(ValidationError):
        OtAutomationPolicy(inter_request_delay_ms=0)
