"""Scan profile and service-family selection for the hardware agent."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Literal

from agent.scanner.models import PortInfo

ScanProfileName = Literal["single-host", "lab", "lan", "deep"]

COMMON_UDP_PORTS = {
    "lab": (53, 67, 68, 69, 123, 137, 161),
    "lan": (53, 67, 68, 123, 137, 161, 1900, 5353),
    "deep": (53, 67, 68, 69, 123, 137, 138, 161, 162, 500, 514, 1900, 5353),
}

TLS_PORTS = {443, 465, 636, 853, 989, 990, 993, 995, 8443, 9443}

SERVICE_SCRIPT_FAMILIES: dict[str, tuple[str, ...]] = {
    "ftp": ("ftp-anon", "ftp-syst"),
    "http": ("http-title", "http-server-header", "http-methods"),
    "https": ("http-title", "http-server-header", "http-methods", "ssl-cert"),
    "microsoft-ds": ("smb2-security-mode", "smb-protocols"),
    "mysql": ("mysql-info",),
    "netbios-ssn": ("smb2-security-mode", "smb-protocols"),
    "rdp": ("rdp-enum-encryption",),
    "redis": ("redis-info",),
    "smtp": ("smtp-commands",),
    "snmp": ("snmp-info",),
    "ssh": ("ssh-auth-methods", "ssh2-enum-algos"),
}


@dataclass(slots=True)
class ScanProfile:
    name: ScanProfileName
    top_ports: int | None
    full_tcp: bool
    version_intensity: int
    udp_ports: tuple[int, ...]
    host_batch_size: int
    max_workers: int

    @property
    def tcp_arguments(self) -> list[str]:
        if self.full_tcp:
            return ["-p-", "--min-rate", "1000", "-sS"]
        return ["--top-ports", str(self.top_ports or 200), "-sS"]


def resolve_scan_profile(name: ScanProfileName) -> ScanProfile:
    if name == "single-host":
        return ScanProfile(
            name=name,
            top_ports=1000,
            full_tcp=False,
            version_intensity=7,
            udp_ports=(53, 123, 161),
            host_batch_size=1,
            max_workers=2,
        )
    if name == "lab":
        return ScanProfile(
            name=name,
            top_ports=1500,
            full_tcp=False,
            version_intensity=7,
            udp_ports=COMMON_UDP_PORTS["lab"],
            host_batch_size=4,
            max_workers=4,
        )
    if name == "deep":
        return ScanProfile(
            name=name,
            top_ports=None,
            full_tcp=True,
            version_intensity=9,
            udp_ports=COMMON_UDP_PORTS["deep"],
            host_batch_size=4,
            max_workers=4,
        )
    return ScanProfile(
        name="lan",
        top_ports=300,
        full_tcp=False,
        version_intensity=5,
        udp_ports=COMMON_UDP_PORTS["lan"],
        host_batch_size=8,
        max_workers=4,
    )


def scripts_for_host(
    ports: list[PortInfo],
    *,
    vulners_script: str = "vulners",
) -> tuple[str, ...]:
    """Return a deduplicated, service-oriented NSE script set for a host."""

    scripts = {vulners_script}
    for port in ports:
        if port.state != "open":
            continue

        service = (port.service.name or "").strip().lower()
        scripts.update(SERVICE_SCRIPT_FAMILIES.get(service, ()))

        if service in {"ssl", "tls"} or port.port in TLS_PORTS:
            scripts.add("ssl-cert")

        if port.protocol == "udp":
            if port.port in {53}:
                scripts.add("dns-recursion")
            if port.port in {161}:
                scripts.add("snmp-info")

    return tuple(sorted(scripts))


def summarize_scripts(ports: list[PortInfo]) -> str:
    """Return a compact summary of the detected services for metadata."""

    service_names = {
        (port.service.name or f"{port.protocol}/{port.port}").lower()
        for port in ports
        if port.state == "open"
    }
    return ",".join(sorted(service_names)) or "none"


def host_sort_key(ip: str) -> tuple[int, ...]:
    return tuple(int(octet) for octet in IPv4Address(ip).exploded.split("."))
