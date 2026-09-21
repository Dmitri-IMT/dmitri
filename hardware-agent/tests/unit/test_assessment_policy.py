from __future__ import annotations

from agent.assessment.policy import (
    EXPOSURE_ROLE_PORTS,
    EXPOSURE_ROLE_TOKENS,
    LOCAL_ASSESSMENT_POLICY_VERSION,
    MACHINE_SIGNAL_RULES,
    MAX_CONFLICTS,
    MAX_EVIDENCE_ITEMS,
    MAX_EVIDENCE_SOURCE_CHARS,
    MAX_EVIDENCE_VALUE_CHARS,
    MAX_LIMITATIONS,
    MAX_REASON_CHARS,
    OS_DEVICE_TYPE_RULES,
    REVIEW_ROLES,
    SIGNAL_WEIGHTS,
)


def test_policy_version_is_frozen() -> None:
    assert LOCAL_ASSESSMENT_POLICY_VERSION == "2026-09-15.2"


def test_signal_weights_and_output_bounds_are_exact() -> None:
    assert SIGNAL_WEIGHTS == {
        "protocol": 3,
        "industrial": 3,
        "product": 2,
        "cpe": 2,
        "operating_system": 2,
        "manufacturer": 1,
        "hostname": 1,
        "service": 1,
        "port": 1,
    }
    assert (
        MAX_EVIDENCE_SOURCE_CHARS,
        MAX_EVIDENCE_VALUE_CHARS,
        MAX_REASON_CHARS,
        MAX_EVIDENCE_ITEMS,
        MAX_CONFLICTS,
        MAX_LIMITATIONS,
    ) == (80, 160, 240, 12, 5, 5)


def test_machine_signal_tables_keep_the_approved_vocabulary() -> None:
    assert set(MACHINE_SIGNAL_RULES) == {
        "router",
        "computer",
        "camera",
        "storage",
        "tv",
        "phone",
        "printer",
        "sensor",
        "unknown",
    }
    assert MACHINE_SIGNAL_RULES["camera"]["service"] == (
        554,
        8554,
        "rtsp",
        "onvif",
    )
    assert MACHINE_SIGNAL_RULES["computer"]["service"] == (
        22,
        445,
        3389,
        5900,
        "ssh",
        "microsoft-ds",
        "ms-wbt-server",
        "vnc",
    )
    assert OS_DEVICE_TYPE_RULES["wap"] == "router"
    assert OS_DEVICE_TYPE_RULES["general purpose"] == "computer"
    assert OS_DEVICE_TYPE_RULES["media device"] == "tv"


def test_exposure_role_tables_keep_conservative_matches() -> None:
    assert EXPOSURE_ROLE_TOKENS["administration"] == (
        "management",
        "webadmin",
        "admin console",
        "routeros",
    )
    assert EXPOSURE_ROLE_TOKENS["api"] == (
        "openapi",
        "swagger",
        "api documentation",
    )
    assert 21 in EXPOSURE_ROLE_PORTS["file_sharing"]
    assert 22 in EXPOSURE_ROLE_PORTS["remote_access"]
    assert 502 in EXPOSURE_ROLE_PORTS["device_control"]
    assert EXPOSURE_ROLE_PORTS["administration"] == ()
    assert REVIEW_ROLES == {
        "administration",
        "api",
        "data_store",
        "file_sharing",
        "remote_access",
        "proxy",
        "device_control",
        "unknown",
    }
