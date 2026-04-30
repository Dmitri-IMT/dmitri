"""Service detection stage for the scanning pipeline."""

from __future__ import annotations

from agent.scanner.models import PortInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.profiles import ScanProfile
from agent.utils.nmap_xml import parse_ports


def detect_services(
    runner: NmapRunner,
    ip: str,
    ports: list[PortInfo],
    profile: ScanProfile,
    *,
    output_xml_path: str | None = None,
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
        str(profile.version_intensity),
        "-p",
        ",".join(
            f"{'T' if port.protocol == 'tcp' else 'U'}:{port.port}"
            for port in open_ports
        ),
        ip,
    ]
    root = runner.run_xml(arguments, output_path=output_xml_path)
    host_element = root.find("host")
    if host_element is None:
        return []
    return parse_ports(host_element)
