from __future__ import annotations

import socket
from types import SimpleNamespace

from agent.utils.network import (
    AvailableSubnetInfo,
    detect_available_subnets,
    detect_local_network,
)


class _FakeSocket:
    def connect(self, _address: tuple[str, int]) -> None:
        return None

    def getsockname(self) -> tuple[str, int]:
        return ("192.168.15.153", 12345)

    def close(self) -> None:
        return None


def test_detect_local_network_resolves_matching_interface(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: _FakeSocket())
    monkeypatch.setattr(
        "agent.utils.network.psutil.net_if_addrs",
        lambda: {
            "Wi-Fi": [
                SimpleNamespace(
                    family=SimpleNamespace(name="AF_INET"),
                    address="192.168.15.153",
                    netmask="255.255.255.0",
                )
            ]
        },
    )

    info = detect_local_network()

    assert info.ip == "192.168.15.153"
    assert info.netmask == "255.255.255.0"
    assert info.subnet == "192.168.15.0/24"
    assert info.interface == "Wi-Fi"


def _addr(
    address: str, netmask: str | None, family: str = "AF_INET"
) -> SimpleNamespace:
    return SimpleNamespace(
        family=SimpleNamespace(name=family),
        address=address,
        netmask=netmask,
    )


def _install_psutil(
    monkeypatch, addrs: dict, up: dict[str, bool] | None = None
) -> None:
    stats = {name: SimpleNamespace(isup=True) for name in addrs}
    for name, isup in (up or {}).items():
        stats[name] = SimpleNamespace(isup=isup)
    monkeypatch.setattr("agent.utils.network.psutil.net_if_addrs", lambda: addrs)
    monkeypatch.setattr("agent.utils.network.psutil.net_if_stats", lambda: stats)


def _install_outbound_ip(monkeypatch, ip: str | None) -> None:
    def _factory(*_args, **_kwargs):
        if ip is None:
            raise OSError("no route to host")
        socket_obj = _FakeSocket()
        socket_obj.getsockname = lambda: (ip, 12345)
        return socket_obj

    monkeypatch.setattr(socket, "socket", _factory)


def test_detect_available_subnets_dual_homed_marks_one_default_route(
    monkeypatch,
) -> None:
    _install_outbound_ip(monkeypatch, "192.168.15.153")
    _install_psutil(
        monkeypatch,
        {
            "eth0": [_addr("10.0.0.7", "255.255.255.0")],
            "wlan0": [_addr("192.168.15.153", "255.255.255.0")],
        },
    )

    subnets = detect_available_subnets()

    assert subnets == [
        AvailableSubnetInfo("eth0", "10.0.0.0/24", False),
        AvailableSubnetInfo("wlan0", "192.168.15.0/24", True),
    ]


def test_detect_available_subnets_single_homed_returns_one_entry(monkeypatch) -> None:
    _install_outbound_ip(monkeypatch, "192.168.15.153")
    _install_psutil(
        monkeypatch,
        {"wlan0": [_addr("192.168.15.153", "255.255.255.0")]},
    )

    subnets = detect_available_subnets()

    assert subnets == [AvailableSubnetInfo("wlan0", "192.168.15.0/24", True)]


def test_detect_available_subnets_excludes_unusable_addresses(monkeypatch) -> None:
    _install_outbound_ip(monkeypatch, "192.168.15.153")
    _install_psutil(
        monkeypatch,
        {
            "lo": [_addr("127.0.0.1", "255.0.0.0")],
            "eth1": [_addr("169.254.10.5", "255.255.0.0")],
            "eth2": [_addr("172.16.0.4", "255.255.255.0")],
            "eth3": [_addr("10.1.2.3", None)],
            "eth4": [_addr("10.1.2.4", "999.255.255.0")],
            "wlan0": [
                _addr("fe80::1", "ffff:ffff:ffff:ffff::", family="AF_INET6"),
                _addr("192.168.15.153", "255.255.255.0"),
            ],
        },
        up={"eth2": False},
    )

    subnets = detect_available_subnets()

    assert subnets == [AvailableSubnetInfo("wlan0", "192.168.15.0/24", True)]


def test_detect_available_subnets_deduplicates_identical_entries(monkeypatch) -> None:
    _install_outbound_ip(monkeypatch, "192.168.15.153")
    _install_psutil(
        monkeypatch,
        {
            "wlan0": [
                _addr("192.168.15.153", "255.255.255.0"),
                _addr("192.168.15.153", "255.255.255.0"),
                _addr("192.168.15.20", "255.255.255.0"),
            ]
        },
    )

    subnets = detect_available_subnets()

    assert subnets == [AvailableSubnetInfo("wlan0", "192.168.15.0/24", True)]


def test_detect_available_subnets_without_default_route_marks_all_false(
    monkeypatch,
) -> None:
    _install_outbound_ip(monkeypatch, None)
    _install_psutil(
        monkeypatch,
        {
            "eth0": [_addr("10.0.0.7", "255.255.255.0")],
            "wlan0": [_addr("192.168.15.153", "255.255.255.0")],
        },
    )

    subnets = detect_available_subnets()

    assert [entry.cidr for entry in subnets] == ["10.0.0.0/24", "192.168.15.0/24"]
    assert all(entry.is_default_route is False for entry in subnets)
