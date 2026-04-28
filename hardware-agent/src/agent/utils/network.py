"""Helpers for resolving the active local IPv4 subnet."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass

import psutil


@dataclass(slots=True)
class LocalNetworkInfo:
    """Detected network details for the active outbound interface."""

    ip: str
    netmask: str
    subnet: str
    interface: str


def detect_local_network() -> LocalNetworkInfo:
    """Resolve the active IPv4 address and subnet used for outbound traffic."""

    local_ip = _detect_local_ip()
    for interface_name, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            family_name = getattr(address.family, "name", "")
            if family_name != "AF_INET":
                continue
            if address.address != local_ip or not address.netmask:
                continue

            subnet = ipaddress.IPv4Network(
                f"{address.address}/{address.netmask}",
                strict=False,
            )
            return LocalNetworkInfo(
                ip=address.address,
                netmask=address.netmask,
                subnet=str(subnet),
                interface=interface_name,
            )

    raise RuntimeError(
        "Could not resolve the active IPv4 subnet from local network interfaces."
    )


def _detect_local_ip() -> str:
    socket_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        socket_obj.connect(("8.8.8.8", 80))
        return socket_obj.getsockname()[0]
    finally:
        socket_obj.close()
