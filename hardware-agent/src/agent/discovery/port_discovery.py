"""Port discovery stage for the scanning pipeline."""

from __future__ import annotations

from agent.scanner.models import PortInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.profiles import ScanProfile
from agent.utils.nmap_xml import extract_ipv4, parse_ports


def scan_ports_batch(
    runner: NmapRunner,
    ips: list[str],
    profile: ScanProfile,
    *,
    output_xml_path: str | None = None,
) -> dict[str, list[PortInfo]]:
    """Enumerate ports for a batch of hosts in one Nmap process."""

    if not ips:
        return {}

    arguments = ["-Pn", "-T4", *profile.tcp_arguments]
    arguments.extend(ips)

    root = runner.run_xml(arguments, output_path=output_xml_path)
    results: dict[str, list[PortInfo]] = {ip: [] for ip in ips}
    for host_element in root.findall("host"):
        ip = extract_ipv4(host_element)
        if not ip:
            continue
        results[ip] = parse_ports(host_element)
    return results


def scan_udp_ports_batch(
    runner: NmapRunner,
    ips: list[str],
    udp_ports: tuple[int, ...],
    *,
    output_xml_path: str | None = None,
) -> dict[str, list[PortInfo]]:
    """Enumerate a selective UDP set for a batch of hosts."""

    if not ips or not udp_ports:
        return {ip: [] for ip in ips}

    arguments = [
        "-Pn",
        "-T3",
        "-sU",
        "--max-retries",
        "1",
        "--defeat-icmp-ratelimit",
        "-p",
        ",".join(str(port) for port in udp_ports),
        *ips,
    ]
    root = runner.run_xml(arguments, output_path=output_xml_path)
    results: dict[str, list[PortInfo]] = {ip: [] for ip in ips}
    for host_element in root.findall("host"):
        ip = extract_ipv4(host_element)
        if not ip:
            continue
        results[ip] = parse_ports(host_element)
    return results
