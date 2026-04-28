"""Port discovery stage for the scanning pipeline."""

from __future__ import annotations

from agent.scanner.models import PortInfo
from agent.scanner.nmap import NmapRunner
from agent.utils.nmap_xml import extract_ipv4, parse_ports


def scan_ports(runner: NmapRunner, ip: str, scan_mode: str) -> list[PortInfo]:
    """Enumerate open and filtered ports for a single host."""

    arguments = ["-Pn", "-T4"]
    if scan_mode == "full":
        arguments.extend(["-p-", "--min-rate", "1000"])
    else:
        arguments.append("-F")
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

    arguments = ["-Pn", "-T4"]
    if scan_mode == "full":
        arguments.extend(["-p-", "--min-rate", "1000"])
    else:
        arguments.append("-F")
    arguments.extend(ips)

    root = runner.run_xml(arguments)
    results: dict[str, list[PortInfo]] = {ip: [] for ip in ips}
    for host_element in root.findall("host"):
        ip = extract_ipv4(host_element)
        if not ip:
            continue
        results[ip] = parse_ports(host_element)
    return results
