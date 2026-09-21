"""Pure local assessment of accepted scanner evidence."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Iterable

from agent.normalize.contracts import DeviceProfilePayload, ExposurePayload
from agent.scanner.models import HostInfo, PortInfo

from .evidence import _port_evidence_key
from .exposure import _exposure_for
from .policy import MachineType
from .profile import _profile_host


@dataclass(slots=True)
class AssessmentResult:
    """Assessment output keyed by the host identity used in the payload."""

    machine_types: dict[str, MachineType]
    device_profiles: dict[str, DeviceProfilePayload]
    exposures: list[ExposurePayload]


def _best_duplicate_port(ports: Iterable[PortInfo]) -> PortInfo:
    return max(ports, key=_port_evidence_key)


def assess_hosts(hosts: Iterable[HostInfo]) -> AssessmentResult:
    """Assess accepted host evidence without performing any I/O."""

    machine_types: dict[str, MachineType] = {}
    device_profiles: dict[str, DeviceProfilePayload] = {}
    exposures: list[ExposurePayload] = []
    ordered_hosts = sorted(hosts, key=lambda host: ip_address(host.ip))
    for host in ordered_hosts:
        machine_type, profile = _profile_host(host)
        machine_types[host.ip] = machine_type
        device_profiles[host.ip] = profile
        endpoints: dict[tuple[str, int], list[PortInfo]] = defaultdict(list)
        for port in host.ports:
            if port.state == "open":
                protocol = port.protocol if port.protocol in {"tcp", "udp"} else "tcp"
                endpoints[(protocol, port.port)].append(port)
        for endpoint in sorted(endpoints):
            port = _best_duplicate_port(endpoints[endpoint])
            exposures.append(_exposure_for(host, port))
    exposures.sort(key=lambda item: (int(item.ip), item.protocol, item.port))
    return AssessmentResult(machine_types, device_profiles, exposures)
