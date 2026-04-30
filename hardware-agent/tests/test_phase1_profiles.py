from __future__ import annotations

from agent.discovery.network_discovery import discovery_arguments_for, infer_target_mode
from agent.scanner.models import PortInfo, ServiceInfo
from agent.scanner.profiles import resolve_scan_profile, scripts_for_host


def test_infer_target_mode_prefers_single_host_or_multi_host() -> None:
    assert infer_target_mode("192.168.0.10", None) == "single_host"
    assert infer_target_mode("192.168.0.10,192.168.0.11", None) == "multi_host"
    assert infer_target_mode(None, "192.168.0.0/24") == "subnet"


def test_discovery_arguments_use_arp_for_same_subnet() -> None:
    arguments = discovery_arguments_for(
        "192.168.0.0/24",
        target_mode="subnet",
        local_subnet="192.168.0.0/24",
    )

    assert arguments == ["-sn", "-PR", "-T4", "192.168.0.0/24"]


def test_discovery_arguments_use_syn_and_ack_for_general_network() -> None:
    arguments = discovery_arguments_for(
        "10.0.0.0/24",
        target_mode="subnet",
        local_subnet="192.168.0.0/24",
    )

    assert arguments == ["-sn", "-PS22,80,443", "-PA22,80,443", "-T4", "10.0.0.0/24"]


def test_service_directed_scripts_follow_detected_services() -> None:
    ports = [
        PortInfo(
            port=22,
            protocol="tcp",
            state="open",
            service=ServiceInfo(name="ssh"),
        ),
        PortInfo(
            port=80,
            protocol="tcp",
            state="open",
            service=ServiceInfo(name="http"),
        ),
        PortInfo(
            port=161,
            protocol="udp",
            state="open",
            service=ServiceInfo(name="snmp"),
        ),
    ]

    scripts = scripts_for_host(ports)

    assert "vulners" in scripts
    assert "ssh-auth-methods" in scripts
    assert "http-methods" in scripts
    assert "snmp-info" in scripts


def test_deep_profile_enables_full_tcp_and_broader_udp() -> None:
    profile = resolve_scan_profile("deep")

    assert profile.full_tcp is True
    assert profile.top_ports is None
    assert 1900 in profile.udp_ports
