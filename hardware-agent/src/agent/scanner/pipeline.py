"""End-to-end Nmap scan orchestration for the hardware agent."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from agent.config import AgentSettings
from agent.discovery.network_discovery import discover_hosts
from agent.discovery.port_discovery import scan_ports_batch
from agent.discovery.vulnerability_detection import run_nse_vulnerability_scan
from agent.normalize.contracts import DevicePayload, PortPayload, ScanPayload
from agent.normalize.findings import extract_findings
from agent.scanner.models import HostInfo, PortInfo
from agent.scanner.nmap import NmapRunner
from agent.utils.network import LocalNetworkInfo, detect_local_network

LOGGER = logging.getLogger(__name__)
AGENT_VERSION = "0.1.0"


class ScanOrchestrator:
    """Run the documented multi-stage scan pipeline."""

    def __init__(
        self,
        settings: AgentSettings,
        runner: NmapRunner | None = None,
    ) -> None:
        self.settings = settings
        self.runner = runner or NmapRunner(settings.nmap_path)
        self.scan_id = uuid4()
        self.started_at: datetime | None = None
        self.current_stage = "idle"
        self.hosts: list[HostInfo] = []
        self.network_info: LocalNetworkInfo | None = None

    def run(self) -> ScanPayload:
        """Execute discovery, service detection, NSE correlation, and normalization."""

        started_at = perf_counter()
        self.started_at = datetime.now(timezone.utc)
        self.current_stage = "discovery"
        self.network_info = self._resolve_network_info()

        self.hosts = discover_hosts(self.runner, self.network_info.subnet)
        LOGGER.info(
            "Discovered %s live hosts in %s.",
            len(self.hosts),
            self.network_info.subnet,
        )

        if self.hosts:
            self._run_port_stage(self.hosts)
            self._run_deep_inspection_stage(self.hosts)

        findings = extract_findings(self.hosts)
        elapsed_seconds = round(perf_counter() - started_at, 2)
        completed_at = datetime.now(timezone.utc)
        self.current_stage = "completed"
        payload = ScanPayload(
            scan_id=self.scan_id,
            timestamp=completed_at,
            subnet=self.network_info.subnet,
            scan_mode=self.settings.scan_mode,
            devices=[self._build_device_payload(host) for host in self.hosts],
            findings=findings,
            metadata=self._build_metadata(
                elapsed_seconds=elapsed_seconds,
                hosts_discovered=len(self.hosts),
                findings_count=len(findings),
            ),
        )
        return payload

    def write_payload(
        self,
        payload: ScanPayload,
        output_path: str | None = None,
    ) -> Path:
        """Persist the normalized payload to disk."""

        target = Path(output_path or self.settings.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return target

    def build_partial_payload(
        self,
        interrupted_stage: str | None = None,
    ) -> ScanPayload:
        """Build a best-effort payload from the progress completed so far."""

        findings = extract_findings(self.hosts)
        started_at = self.started_at or datetime.now(timezone.utc)
        elapsed_seconds = round(
            (datetime.now(timezone.utc) - started_at).total_seconds(),
            2,
        )
        stage = interrupted_stage or self.current_stage
        return ScanPayload(
            scan_id=self.scan_id,
            timestamp=datetime.now(timezone.utc),
            subnet=self._resolve_network_info().subnet,
            scan_mode=self.settings.scan_mode,
            devices=[self._build_device_payload(host) for host in self.hosts],
            findings=findings,
            metadata=self._build_metadata(
                elapsed_seconds=elapsed_seconds,
                hosts_discovered=len(self.hosts),
                findings_count=len(findings),
                partial_result=True,
                interrupted_stage=stage,
            ),
        )

    def _run_port_stage(self, hosts: list[HostInfo]) -> None:
        self.current_stage = "port_scan"
        LOGGER.info(
            "Starting port scan stage for %s hosts using batches of %s.",
            len(hosts),
            self.settings.host_batch_size,
        )
        batches = _chunked(
            [host.ip for host in hosts],
            self.settings.host_batch_size,
        )
        host_map = {host.ip: host for host in hosts}
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            futures = {
                executor.submit(
                    scan_ports_batch,
                    self.runner,
                    batch,
                    self.settings.scan_mode,
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

    def _run_deep_inspection_stage(self, hosts: list[HostInfo]) -> None:
        self.current_stage = "deep_inspection"
        eligible_hosts = [host for host in hosts if host.open_ports]
        LOGGER.info(
            "Starting deep inspection stage for %s hosts with open ports.",
            len(eligible_hosts),
        )
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            futures = {
                executor.submit(
                    run_nse_vulnerability_scan,
                    self.runner,
                    host.ip,
                    host.ports,
                    version_intensity=self.settings.version_intensity,
                    scripts=self.settings.nmap_scripts,
                    min_cvss=self.settings.min_cvss,
                ): host
                for host in eligible_hosts
            }
            for future in as_completed(futures):
                host = futures[future]
                result = future.result()
                if result is None:
                    continue
                host.ports = _merge_ports(host.ports, result.ports)
                host.host_scripts = result.host_scripts
                LOGGER.info(
                    "Deep inspection finished for %s with %s open ports "
                    "and %s host scripts.",
                    host.ip,
                    len(host.open_ports),
                    len(host.host_scripts),
                )

    def _build_device_payload(self, host: HostInfo) -> DevicePayload:
        return DevicePayload(
            ip=host.ip,
            mac=host.mac,
            hostname=host.hostname or host.ip,
            vendor=host.vendor or "unknown",
            ports=[
                    PortPayload(
                        port=port.port,
                        protocol=(
                            port.protocol if port.protocol in {"tcp", "udp"} else "tcp"
                        ),
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

    def _nmap_arguments_summary(self) -> str:
        port_stage = (
            "-p- --min-rate 1000" if self.settings.scan_mode == "full" else "-F"
        )
        return (
            f"discovery=-sn -PE -T4; ports={port_stage} -Pn -T4; "
            "deep_inspection="
            f"-sV --version-intensity {self.settings.version_intensity}; "
            "scripts="
            f"{','.join(self.settings.nmap_scripts)}; "
            f"min_cvss={self.settings.min_cvss}; "
            f"workers={self.settings.max_workers}; "
            f"host_batch_size={self.settings.host_batch_size}"
        )

    def _build_metadata(
        self,
        *,
        elapsed_seconds: float,
        hosts_discovered: int,
        findings_count: int,
        partial_result: bool = False,
        interrupted_stage: str | None = None,
    ) -> dict[str, str | int | float | bool]:
        metadata: dict[str, str | int | float | bool] = {
            "agent_version": AGENT_VERSION,
            "nmap_path": self.runner.nmap_path,
            "nmap_arguments": self._nmap_arguments_summary(),
            "elapsed_seconds": elapsed_seconds,
            "hosts_discovered": hosts_discovered,
            "findings_count": findings_count,
            "min_cvss": self.settings.min_cvss,
            "max_workers": self.settings.max_workers,
            "host_batch_size": self.settings.host_batch_size,
            "partial_result": partial_result,
        }
        if self.network_info is not None:
            metadata["detected_local_ip"] = self.network_info.ip
            metadata["detected_netmask"] = self.network_info.netmask
            metadata["detected_interface"] = self.network_info.interface
            metadata["scan_subnet_source"] = (
                "environment" if self.settings.scan_subnet else "autodetected"
            )
        if interrupted_stage:
            metadata["interrupted_stage"] = interrupted_stage
        return metadata

    def _resolve_network_info(self) -> LocalNetworkInfo:
        if self.network_info is not None:
            return self.network_info

        detected = detect_local_network()
        if self.settings.scan_subnet:
            LOGGER.info(
                "Using configured subnet %s. Active interface %s has IPv4 %s.",
                self.settings.scan_subnet,
                detected.interface,
                detected.ip,
            )
            self.network_info = LocalNetworkInfo(
                ip=detected.ip,
                netmask=detected.netmask,
                subnet=self.settings.scan_subnet,
                interface=detected.interface,
            )
        else:
            LOGGER.info(
                "Auto-detected subnet %s from interface %s (%s/%s).",
                detected.subnet,
                detected.interface,
                detected.ip,
                detected.netmask,
            )
            self.network_info = detected
        return self.network_info


def _merge_ports(
    existing_ports: list[PortInfo],
    new_ports: list[PortInfo],
) -> list[PortInfo]:
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


def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    return [
        items[index : index + chunk_size]
        for index in range(0, len(items), chunk_size)
    ]
