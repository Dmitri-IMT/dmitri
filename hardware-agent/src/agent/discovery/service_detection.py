"""Service detection stage for the scanning pipeline."""

from __future__ import annotations

from agent.scanner.models import PortInfo
from agent.scanner.nmap import NmapRunner
from agent.utils.nmap_xml import parse_ports


def detect_services(
    runner: NmapRunner,
    ip: str,
    ports: list[PortInfo],
    version_intensity: int,
) -> list[PortInfo]:
    """Run `-sV` over the discovered open ports for a single host."""

    open_ports = [port for port in ports if port.state == "open"]
    if not open_ports:
        return []

    arguments = [
        "-Pn",
        "-T4",
        "-sV",
        "--version-intensity",
        str(version_intensity),
        "-p",
        ",".join(str(port.port) for port in open_ports),
        ip,
    ]
    root = runner.run_xml(arguments)
    host_element = root.find("host")
    if host_element is None:
        return []
    return parse_ports(host_element)
