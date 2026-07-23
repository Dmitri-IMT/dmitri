from __future__ import annotations

from api.services.hosts import identity_key


def test_identity_key_prefers_mac_and_upper_cases():
    assert identity_key("b8:27:eb:44:55:66", "192.168.1.10") == "mac:B8:27:EB:44:55:66"


def test_identity_key_falls_back_to_ip_when_mac_none():
    assert identity_key(None, "192.168.1.10") == "ip:192.168.1.10"


def test_identity_key_falls_back_to_ip_when_mac_empty_string():
    assert identity_key("", "192.168.1.10") == "ip:192.168.1.10"
