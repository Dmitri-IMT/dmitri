"""Host discovery stage for the scanning pipeline."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.scanner.models import HostInfo
from agent.scanner.nmap import NmapRunner


def discover_hosts(
    runner: NmapRunner,
    subnet: str,
    timeout: float | None = None,
) -> list[HostInfo]:
    """Return live hosts discovered by Nmap host discovery."""

    root = runner.run_xml(["-sn", "-PE", "-T4", subnet], timeout=timeout)
    hosts: list[HostInfo] = []
    for host_element in root.findall("host"):
        parsed = _parse_host(host_element)
        if parsed is not None:
            hosts.append(parsed)
    return hosts


def _parse_host(host_element: ET.Element) -> HostInfo | None:
    status_node = host_element.find("status")
    if status_node is None or status_node.get("state") != "up":
        return None

    ip = ""
    mac: str | None = None
    vendor = "unknown"
    for address_node in host_element.findall("address"):
        address_type = address_node.get("addrtype")
        if address_type == "ipv4":
            ip = address_node.get("addr", "")
        elif address_type == "mac":
            mac = address_node.get("addr")
            vendor = address_node.get("vendor", "unknown")

    if not ip:
        return None

    hostname = ip
    hostnames_node = host_element.find("hostnames")
    if hostnames_node is not None:
        hostname_node = hostnames_node.find("hostname")
        if hostname_node is not None and hostname_node.get("name"):
            hostname = hostname_node.get("name", ip)

    return HostInfo(ip=ip, hostname=hostname, mac=mac, vendor=vendor)
