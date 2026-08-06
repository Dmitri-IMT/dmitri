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


@dataclass(slots=True)
class AvailableSubnetInfo:
    """One usable IPv4 subnet reachable from a local interface."""

    interface: str
    cidr: str
    is_default_route: bool


def detect_available_subnets() -> list[AvailableSubnetInfo]:
    try:
        default_interface: str | None = detect_local_network().interface
    except (OSError, RuntimeError, ValueError):
        default_interface = None

    stats = psutil.net_if_stats()
    subnets: list[AvailableSubnetInfo] = []
    seen: set[tuple[str, str]] = set()
    for interface_name, addresses in psutil.net_if_addrs().items():
        interface_stats = stats.get(interface_name)
        if interface_stats is None or not interface_stats.isup:
            continue
        for address in addresses:
            if getattr(address.family, "name", "") != "AF_INET":
                continue
            if not address.address or not address.netmask:
                continue
            try:
                host = ipaddress.IPv4Address(address.address)
                network = ipaddress.IPv4Network(
                    f"{address.address}/{address.netmask}",
                    strict=False,
                )
            except ValueError:
                continue
            if host.is_loopback or host.is_link_local:
                continue
            key = (interface_name, str(network))
            if key in seen:
                continue
            seen.add(key)
            subnets.append(
                AvailableSubnetInfo(
                    interface=interface_name,
                    cidr=str(network),
                    is_default_route=interface_name == default_interface,
                )
            )
    return subnets


class NetworkUnreachableError(RuntimeError):
    """Raised when no usable network path exists to run a scan."""


def check_network_connectivity() -> None:
    """Verify that at least one non-loopback IPv4 interface is up."""
    for name, stats in psutil.net_if_stats().items():
        if not stats.isup:
            continue
        addrs = psutil.net_if_addrs().get(name, [])
        for addr in addrs:
            if getattr(addr.family, "name", "") != "AF_INET":
                continue
            if addr.address and not addr.address.startswith("127."):
                return
    raise NetworkUnreachableError(
        "No active network interface found. "
        "Cannot run scan — check your network connection."
    )


def _detect_local_ip() -> str:
    socket_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        socket_obj.connect(("8.8.8.8", 80))
        return socket_obj.getsockname()[0]
    finally:
        socket_obj.close()
