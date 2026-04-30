"""Host discovery stage for the scanning pipeline."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from ipaddress import IPv4Address, IPv4Network, ip_network, summarize_address_range

from agent.scanner.models import HostInfo
from agent.scanner.nmap import NmapRunner


def discover_hosts(
    runner: NmapRunner,
    target: str,
    *,
    target_mode: str,
    local_subnet: str | None = None,
    output_xml_path: str | None = None,
) -> list[HostInfo]:
    """Return live hosts discovered with the context-appropriate strategy."""

    if target_mode == "single_host":
        return [HostInfo(ip=target, hostname=target)]

    root = runner.run_xml(
        _build_discovery_arguments(
            target=target,
            target_mode=target_mode,
            local_subnet=local_subnet,
        ),
        output_path=output_xml_path,
    )
    hosts: list[HostInfo] = []
    for host_element in root.findall("host"):
        parsed = _parse_host(host_element)
        if parsed is not None:
            hosts.append(parsed)
    return hosts


def discovery_arguments_for(
    target: str,
    *,
    target_mode: str,
    local_subnet: str | None = None,
) -> list[str]:
    """Expose the discovery arguments for metadata and tests."""

    if target_mode == "single_host":
        return ["-Pn", target]
    return _build_discovery_arguments(
        target=target,
        target_mode=target_mode,
        local_subnet=local_subnet,
    )


def _build_discovery_arguments(
    *,
    target: str,
    target_mode: str,
    local_subnet: str | None,
) -> list[str]:
    if target_mode == "subnet" and local_subnet and _same_subnet(target, local_subnet):
        return ["-sn", "-PR", "-T4", target]

    if target_mode == "multi_host":
        hosts = [item.strip() for item in target.split(",") if item.strip()]
        return ["-sn", "-PS22,80,443", "-PA22,80,443", "-T4", *hosts]

    return ["-sn", "-PS22,80,443", "-PA22,80,443", "-T4", target]


def _same_subnet(target: str, local_subnet: str) -> bool:
    try:
        target_net = ip_network(target, strict=False)
        local_net = ip_network(local_subnet, strict=False)
    except ValueError:
        return False
    return target_net == local_net


def infer_target_mode(target: str | None, subnet: str | None) -> str:
    """Infer the target mode from the provided inputs."""

    if target:
        items = [item.strip() for item in target.split(",") if item.strip()]
        if len(items) > 1:
            return "multi_host"
        return "single_host"
    return "subnet"


def summarize_target_scope(target_mode: str, target: str, subnet: str | None) -> str:
    """Return a normalized CIDR-like scope string for payload compatibility."""

    if target_mode == "subnet":
        return subnet or target

    hosts = [IPv4Address(item.strip()) for item in target.split(",") if item.strip()]
    if len(hosts) == 1:
        return f"{hosts[0]}/32"

    lowest = min(hosts)
    highest = max(hosts)
    summarized = list(summarize_address_range(lowest, highest))
    if len(summarized) == 1:
        return str(summarized[0])
    return str(IPv4Network(f"{lowest}/32", strict=False))


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
