from __future__ import annotations

from typing import get_args

from api.core.machine_type import MACHINE_TYPES, MachineType, classify_machine_type

CASES = [
    ("Hikvision", [(554, "rtsp")], "camera"),
    ("Apple", [(22, "ssh")], "computer"),
    ("Apple", [], "phone"),
    ("Nokia", [], "unknown"),
    ("unknown", [], "unknown"),
    ("unknown", [(22, "ssh")], "computer"),
    ("TP-Link", [], "router"),
    ("Espressif Inc.", [], "sensor"),
    ("", [(9999, "rtsp-alt")], "camera"),
    ("", [(554, "")], "camera"),
    ("", [(631, "ipp"), (554, "rtsp")], "camera"),
    ("", [(2049, "nfs"), (53, "domain"), (80, "http")], "storage"),
    ("", [(53, "domain"), (80, "http"), (8008, "http")], "router"),
    ("", [(1883, "mqtt"), (22, "ssh")], "sensor"),
    ("", [(53, "domain"), (443, "https")], "router"),
    ("", [(1900, "upnp"), (53, "domain")], "router"),
    ("", [(1900, "upnp")], "unknown"),
    ("", [(80, "http")], "unknown"),
]


def test_classification():
    for vendor, services, expected in CASES:
        assert classify_machine_type(vendor, services) == expected


def test_result_is_always_a_published_type():
    for vendor, services, _ in CASES:
        assert classify_machine_type(vendor, services) in MACHINE_TYPES


def test_vocabulary_is_exactly_the_nine_literal_members():
    assert MACHINE_TYPES == get_args(MachineType)
    assert len(MACHINE_TYPES) == 9
    assert set(MACHINE_TYPES) == {
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
