"""Port discovery stage for the scanning pipeline."""

from __future__ import annotations

from agent.config import NSPI_PORTS, port_stage_scripts
from agent.scanner.models import PortInfo
from agent.scanner.nmap import NmapRunner
from agent.utils.nmap_xml import extract_ipv4, parse_ports


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
        if new_port.service.name or new_port.service.banner or new_port.service.cpes:
            current.service = new_port.service
        if new_port.scripts:
            current.scripts = new_port.scripts

    return sorted(merged.values(), key=lambda port: (port.port, port.protocol))


def scan_ports(runner: NmapRunner, ip: str, scan_mode: str) -> list[PortInfo]:
    """Enumerate open and filtered ports for a single host."""

    arguments = ["-Pn", "-T4"]
    if scan_mode == "full":
        arguments.extend(["-p-", "--min-rate", "1000"])
    else:
        arguments.extend(["-sV", "-O", "--script", port_stage_scripts(scan_mode)])
    arguments.append(ip)

    root = runner.run_xml(arguments)
    host_element = root.find("host")
    if host_element is None:
        return []
    return parse_ports(host_element)


def scan_ports_batch(
    runner: NmapRunner,
    ips: list[str],
    scan_mode: str,
) -> dict[str, list[PortInfo]]:
    """Enumerate ports for a batch of hosts in one Nmap process."""

    if not ips:
        return {}

    if scan_mode == "nspi":
        return _scan_ports_batch_nspi(runner, ips)

    arguments = ["-Pn", "-T4"]
    if scan_mode == "full":
        arguments.extend(["-p-", "--min-rate", "1000"])
    else:
        arguments.extend(["-sV", "-O", "--script", port_stage_scripts(scan_mode)])
    arguments.extend(ips)

    root = runner.run_xml(arguments)
    results: dict[str, list[PortInfo]] = {ip: [] for ip in ips}
    for host_element in root.findall("host"):
        ip = extract_ipv4(host_element)
        if not ip:
            continue
        results[ip] = parse_ports(host_element)
    return results


def _scan_ports_batch_nspi(
    runner: NmapRunner,
    ips: list[str],
) -> dict[str, list[PortInfo]]:
    """NSPi two-pass port scan: top-1000 + OT-specific ports, merged."""

    results: dict[str, list[PortInfo]] = {ip: [] for ip in ips}

    # Pass 1: top-1000 (no -p flag)
    pass1_args = ["-Pn", "-T2", "-n", "-sV", "-O", *ips]
    root1 = runner.run_xml(pass1_args)
    for host_element in root1.findall("host"):
        ip = extract_ipv4(host_element)
        if ip:
            results[ip] = parse_ports(host_element)

    # Pass 2: OT-specific ports
    pass2_args = ["-Pn", "-T2", "-n", "-p", NSPI_PORTS, "-sV", *ips]
    root2 = runner.run_xml(pass2_args)
    for host_element in root2.findall("host"):
        ip = extract_ipv4(host_element)
        if ip:
            results[ip] = merge_ports(results.get(ip, []), parse_ports(host_element))

    return results
