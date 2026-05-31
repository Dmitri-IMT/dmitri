from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from agent.config import deep_stage_scripts
from agent.discovery.port_discovery import (
    discovery_arguments,
    merge_ports,
    scan_ports_batch,
)
from agent.discovery.vulnerability_detection import run_nse_vulnerability_scan
from agent.normalize.contracts import DevicePayload, PortPayload
from agent.scanner.nmap import AGENT_VERSION, LoggedNmapRunner

if TYPE_CHECKING:
    from agent.config import AgentSettings
    from agent.scanner.models import HostInfo
    from agent.scanner.nmap import NmapRunner
    from agent.utils.network import LocalNetworkInfo

LOGGER = logging.getLogger(__name__)


def set_runner_stage(runner: NmapRunner, stage: str) -> None:
    if isinstance(runner, LoggedNmapRunner):
        runner.set_stage(stage)


def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    return [
        items[index : index + chunk_size] for index in range(0, len(items), chunk_size)
    ]


def run_port_stage(
    runner: NmapRunner,
    settings: AgentSettings,
    hosts: list[HostInfo],
) -> None:
    set_runner_stage(runner, "ports")
    LOGGER.info(
        "Starting port scan stage for %s hosts using batches of %s.",
        len(hosts),
        settings.host_batch_size,
    )
    batches = _chunked([host.ip for host in hosts], settings.host_batch_size)
    host_map = {host.ip: host for host in hosts}
    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {
            executor.submit(
                scan_ports_batch,
                runner,
                batch,
                settings.scan_mode,
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            batch = futures[future]
            results = future.result()
            for ip in batch:
                host = host_map[ip]
                host.ports = sorted(
                    results.get(ip, []),
                    key=lambda port: (port.port, port.protocol),
                )
                LOGGER.info(
                    "Port scan finished for %s with %s ports.",
                    host.ip,
                    len(host.ports),
                )


def run_deep_inspection_stage(
    runner: NmapRunner,
    settings: AgentSettings,
    hosts: list[HostInfo],
) -> None:
    set_runner_stage(runner, "nse")
    eligible_hosts = [host for host in hosts if host.open_ports]
    LOGGER.info(
        "Starting deep inspection stage for %s hosts with open ports.",
        len(eligible_hosts),
    )
    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {
            executor.submit(
                run_nse_vulnerability_scan,
                runner,
                host.ip,
                host.ports,
                version_intensity=settings.version_intensity,
                scripts=deep_stage_scripts(settings.scan_mode, settings.nmap_scripts),
                min_cvss=settings.min_cvss,
            ): host
            for host in eligible_hosts
        }
        for future in as_completed(futures):
            host = futures[future]
            result = future.result()
            if result is None:
                continue
            host.ports = merge_ports(host.ports, result.ports)
            host.host_scripts = result.host_scripts
            LOGGER.info(
                "Deep inspection finished for %s with %s open ports "
                "and %s host scripts.",
                host.ip,
                len(host.open_ports),
                len(host.host_scripts),
            )


def build_device_payload(host: HostInfo) -> DevicePayload:
    return DevicePayload(
        ip=host.ip,
        mac=host.mac,
        hostname=host.hostname or host.ip,
        vendor=host.vendor or "unknown",
        ports=[
            PortPayload(
                port=port.port,
                protocol=(port.protocol if port.protocol in {"tcp", "udp"} else "tcp"),
                state=(
                    port.state
                    if port.state in {"open", "closed", "filtered"}
                    else "open"
                ),
                service=port.service.name or "unknown",
                version=port.service.banner,
            )
            for port in sorted(
                host.ports,
                key=lambda item: (item.port, item.protocol),
            )
        ],
    )


def nmap_arguments_summary(settings: AgentSettings) -> str:
    port_stage = " ".join(discovery_arguments(settings.scan_mode))
    deep_scripts = deep_stage_scripts(settings.scan_mode, settings.nmap_scripts)
    return (
        f"discovery=-sn -PE -T4; ports={port_stage} -Pn -T4; "
        "deep_inspection="
        f"-sV --version-intensity {settings.version_intensity}; "
        "scripts="
        f"{','.join(deep_scripts)}; "
        f"min_cvss={settings.min_cvss}; "
        f"workers={settings.max_workers}; "
        f"host_batch_size={settings.host_batch_size}"
    )


def build_metadata(
    *,
    runner: NmapRunner,
    settings: AgentSettings,
    network_info: LocalNetworkInfo | None,
    elapsed_seconds: float,
    hosts_discovered: int,
    findings_count: int,
    partial_result: bool = False,
    interrupted_stage: str | None = None,
) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {
        "agent_version": AGENT_VERSION,
        "nmap_path": runner.nmap_path,
        "nmap_arguments": nmap_arguments_summary(settings),
        "elapsed_seconds": elapsed_seconds,
        "hosts_discovered": hosts_discovered,
        "findings_count": findings_count,
        "min_cvss": settings.min_cvss,
        "max_workers": settings.max_workers,
        "host_batch_size": settings.host_batch_size,
        "partial_result": partial_result,
    }
    if network_info is not None:
        metadata["detected_local_ip"] = network_info.ip
        metadata["detected_netmask"] = network_info.netmask
        metadata["detected_interface"] = network_info.interface
        metadata["scan_subnet_source"] = (
            "environment" if settings.scan_subnet else "autodetected"
        )
    if interrupted_stage:
        metadata["interrupted_stage"] = interrupted_stage
    return metadata
