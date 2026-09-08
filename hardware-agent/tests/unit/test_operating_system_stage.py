from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.config import AgentSettings
from agent.scanner.models import HostInfo, OperatingSystemInfo, PortInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.stages import run_deep_inspection_stage, run_port_stage


class _ReversedHostRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "nmap"

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        del timeout
        root = ET.Element("nmaprun")
        evidence = {
            "10.0.0.1": (22, "Linux", "96"),
            "10.0.0.2": (502, "Schneider appliance", "88"),
        }
        for ip in reversed(arguments[-2:]):
            port_number, os_name, accuracy = evidence[ip]
            host = ET.SubElement(root, "host")
            ET.SubElement(host, "address", addr=ip, addrtype="ipv4")
            ports = ET.SubElement(host, "ports")
            port = ET.SubElement(
                ports, "port", protocol="tcp", portid=str(port_number)
            )
            ET.SubElement(port, "state", state="open")
            ET.SubElement(port, "service", name="unknown")
            os_element = ET.SubElement(host, "os")
            ET.SubElement(
                os_element,
                "osmatch",
                name=os_name,
                accuracy=accuracy,
            )
        return root


def test_port_stage_associates_ports_and_os_by_ipv4() -> None:
    hosts = [
        HostInfo(ip="10.0.0.1", hostname="host-one"),
        HostInfo(ip="10.0.0.2", hostname="host-two"),
    ]
    settings = AgentSettings(
        scan_mode="standard",
        host_batch_size=2,
        max_workers=1,
    )

    run_port_stage(_ReversedHostRunner(), settings, hosts)

    assert [port.port for port in hosts[0].ports] == [22]
    assert hosts[0].operating_system == OperatingSystemInfo(
        name="Linux", accuracy=96
    )
    assert [port.port for port in hosts[1].ports] == [502]
    assert hosts[1].operating_system == OperatingSystemInfo(
        name="Schneider appliance", accuracy=88
    )


def test_port_stage_attaches_missing_evidence_as_none() -> None:
    class _NoEvidenceRunner(NmapRunner):
        def __init__(self) -> None:
            self.nmap_path = "nmap"

        def run_xml(
            self, arguments: list[str], timeout: float | None = None
        ) -> ET.Element:
            del arguments, timeout
            return ET.fromstring(
                '<nmaprun><host><address addr="10.0.0.3" '
                'addrtype="ipv4" /></host></nmaprun>'
            )

    host = HostInfo(
        ip="10.0.0.3",
        hostname="host-three",
        operating_system=OperatingSystemInfo(name="stale", accuracy=50),
    )
    settings = AgentSettings(
        scan_mode="standard",
        host_batch_size=1,
        max_workers=1,
    )

    run_port_stage(_NoEvidenceRunner(), settings, [host])

    assert host.operating_system is None


def test_deep_inspection_does_not_replace_port_stage_os(
    monkeypatch,
) -> None:
    port_stage_os = OperatingSystemInfo(name="Linux", accuracy=96)
    host = HostInfo(
        ip="10.0.0.4",
        hostname="host-four",
        ports=[PortInfo(port=22)],
        operating_system=port_stage_os,
    )

    def _deep_scan(*args, **kwargs) -> HostInfo:
        del args, kwargs
        return HostInfo(
            ip="10.0.0.4",
            hostname="host-four",
            ports=[PortInfo(port=22)],
            operating_system=OperatingSystemInfo(name="Unrelated", accuracy=100),
        )

    monkeypatch.setattr(
        "agent.scanner.stages.run_nse_vulnerability_scan",
        _deep_scan,
    )

    run_deep_inspection_stage(
        _ReversedHostRunner(),
        AgentSettings(scan_mode="standard", max_workers=1),
        [host],
    )

    assert host.operating_system is port_stage_os
