"""Port discovery stage for the scanning pipeline."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace

from agent.config import NSPI_HOST_TIMEOUT, NSPI_PORTS
from agent.scanner.models import PortInfo, PortScanResult
from agent.scanner.nmap import NmapRunner
from agent.utils.nmap_xml import (
    extract_ipv4,
    extract_mac_identity,
    parse_operating_system,
    parse_ports,
)

NSPI_PASS1_ARGS = ["-Pn", "-T4", "-n", "--host-timeout", NSPI_HOST_TIMEOUT]
NSPI_PASS2_ARGS = [
    "-Pn",
    "-T2",
    "-n",
    "-p",
    NSPI_PORTS,
    "--host-timeout",
    NSPI_HOST_TIMEOUT,
]


def merge_ports(
    existing_ports: list[PortInfo],
    new_ports: list[PortInfo],
) -> list[PortInfo]:
    """Merge two port lists, deduplicating by (port, protocol) key."""
    merged: dict[tuple[int, str], PortInfo] = {
        (port.port, port.protocol): port for port in existing_ports
    }

    for new_port in new_ports:
        key = (new_port.port, new_port.protocol)
        current = merged.get(key)
        if current is None:
            merged[key] = new_port
            continue

        current.state = new_port.state or current.state
        if (
            new_port.service.name
            or new_port.service.banner
            or new_port.service.tunnel
            or new_port.service.cpes
        ):
            current.service = replace(
                new_port.service,
                tunnel=new_port.service.tunnel or current.service.tunnel,
            )
        if new_port.scripts:
            current.scripts = new_port.scripts

    return sorted(merged.values(), key=lambda port: (port.port, port.protocol))


def merge_port_scan_results(
    existing: PortScanResult,
    incoming: PortScanResult,
) -> PortScanResult:
    """Merge port evidence while retaining the strongest OS detection."""

    operating_system = existing.operating_system
    if operating_system is None or (
        incoming.operating_system is not None
        and incoming.operating_system.accuracy > operating_system.accuracy
    ):
        operating_system = incoming.operating_system

    return PortScanResult(
        ports=merge_ports(existing.ports, incoming.ports),
        operating_system=operating_system,
        identity=existing.identity.merged_with(incoming.identity),
        skipped=existing.skipped or incoming.skipped,
    )


def _parse_port_scan_result(host_element: ET.Element) -> PortScanResult:
    return PortScanResult(
        ports=parse_ports(host_element),
        operating_system=parse_operating_system(host_element),
        identity=extract_mac_identity(host_element),
    )


def discovery_arguments(scan_mode: str) -> list[str]:
    if scan_mode == "max":
        return ["-O", "-p-", "--min-rate", "1000"]
    if scan_mode == "extensive":
        return ["-O", "--top-ports", "10000"]
    return ["-O"]


def scan_ports(runner: NmapRunner, ip: str, scan_mode: str) -> PortScanResult:
    """Enumerate open and filtered ports for a single host."""

    arguments = ["-Pn", "-n", "-T4", *discovery_arguments(scan_mode), ip]

    root = runner.run_xml(arguments)
    host_element = root.find("host")
    if host_element is None:
        return PortScanResult()
    return _parse_port_scan_result(host_element)


def scan_ports_batch(
    runner: NmapRunner,
    ips: list[str],
    scan_mode: str,
    timeout: float | None = None,
) -> dict[str, PortScanResult]:
    """Enumerate ports for a batch of hosts in one Nmap process."""

    if not ips:
        return {}

    if scan_mode == "nspi":
        return _scan_ports_batch_nspi(runner, ips, timeout=timeout)

    arguments = ["-Pn", "-n", "-T4", *discovery_arguments(scan_mode), *ips]

    root = runner.run_xml(arguments, timeout=timeout)
    results = {ip: PortScanResult() for ip in ips}
    for host_element in root.findall("host"):
        ip = extract_ipv4(host_element)
        if not ip:
            continue
        results[ip] = _parse_port_scan_result(host_element)
    return results


def _scan_ports_batch_nspi(
    runner: NmapRunner,
    ips: list[str],
    timeout: float | None = None,
) -> dict[str, PortScanResult]:
    """NSPi two-pass port scan: top-1000 + OT-specific ports, merged."""

    results = {ip: PortScanResult() for ip in ips}
    pass1_hosts: set[str] = set()
    pass2_hosts: set[str] = set()

    # Pass 1: top-1000 (no -p flag)
    pass1_args = [*NSPI_PASS1_ARGS, *ips]
    root1 = runner.run_xml(pass1_args, timeout=timeout)
    for host_element in root1.findall("host"):
        ip = extract_ipv4(host_element)
        if ip:
            pass1_hosts.add(ip)
            results[ip] = _parse_port_scan_result(host_element)

    # Pass 2: OT-specific ports
    pass2_args = [*NSPI_PASS2_ARGS, *ips]
    root2 = runner.run_xml(pass2_args, timeout=timeout)
    for host_element in root2.findall("host"):
        ip = extract_ipv4(host_element)
        if ip:
            pass2_hosts.add(ip)
            results[ip] = merge_port_scan_results(
                results.get(ip, PortScanResult()),
                _parse_port_scan_result(host_element),
            )

    for ip in ips:
        results[ip].skipped = ip not in pass1_hosts or ip not in pass2_hosts

    return results
