from __future__ import annotations

import socket
from types import SimpleNamespace

from agent.utils.network import detect_local_network


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
