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
from agent.discovery.network_discovery import (
    discover_hosts,
    discovery_arguments_for,
    infer_target_mode,
    summarize_target_scope,
)
from agent.discovery.port_discovery import scan_ports_batch, scan_udp_ports_batch
from agent.discovery.service_detection import detect_services
from agent.discovery.vulnerability_detection import run_targeted_nse_scan
from agent.normalize.contracts import (
    ArtifactPayload,
    DevicePayload,
    PortPayload,
    ScanPayload,
)
from agent.normalize.findings import extract_findings
from agent.scanner.models import HostInfo, PortInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.profiles import (
    ScanProfile,
    host_sort_key,
    resolve_scan_profile,
    scripts_for_host,
)
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
        self.target_mode = settings.target_mode or "subnet"
        self.scan_scope = settings.scan_subnet or ""
        self.scan_target = settings.scan_target or ""
        self.profile: ScanProfile | None = None
        self.artifacts: list[ArtifactPayload] = []

    def run(self) -> ScanPayload:
        """Execute discovery, service detection, NSE correlation, and normalization."""

        started_at = perf_counter()
        self.started_at = datetime.now(timezone.utc)
        self.network_info = self._resolve_network_info()
        self.target_mode = self.settings.target_mode or infer_target_mode(
            self.settings.scan_target,
            self.settings.scan_subnet,
        )
        self.scan_target = self._resolve_scan_target()
        self.scan_scope = summarize_target_scope(
            self.target_mode,
            self.scan_target,
            self.settings.scan_subnet or self.network_info.subnet,
        )
        self.profile = resolve_scan_profile(self.settings.scan_profile)

        self.current_stage = "discovery"
        discovery_xml = self._artifact_file("discovery", "discovery.xml")
        self.hosts = discover_hosts(
            self.runner,
            self.scan_target,
            target_mode=self.target_mode,
            local_subnet=self.network_info.subnet,
            output_xml_path=discovery_xml,
        )
        if discovery_xml is not None:
            self._record_artifact("nmap_xml", discovery_xml, "discovery")
        self.hosts.sort(key=lambda host: host_sort_key(host.ip))
        LOGGER.info(
            "Discovered %s live hosts in %s.",
            len(self.hosts),
            self.scan_scope,
        )

        if self.hosts:
            self._run_tcp_port_stage(self.hosts)
            self._run_udp_port_stage(self.hosts)
            self._run_service_stage(self.hosts)
            self._run_nse_stage(self.hosts)

        findings = extract_findings(self.hosts)
        elapsed_seconds = round(perf_counter() - started_at, 2)
        completed_at = datetime.now(timezone.utc)
        self.current_stage = "completed"
        payload = ScanPayload(
            scan_id=self.scan_id,
            timestamp=completed_at,
            subnet=self.scan_scope,
            target_mode=self.target_mode,  # type: ignore[arg-type]
            scan_profile=self.settings.scan_profile,
            devices=[self._build_device_payload(host) for host in self.hosts],
            findings=findings,
            artifacts=self.artifacts,
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
            subnet=self.scan_scope or self._resolve_network_info().subnet,
            target_mode=self.target_mode,  # type: ignore[arg-type]
            scan_profile=self.settings.scan_profile,
            devices=[self._build_device_payload(host) for host in self.hosts],
            findings=findings,
            artifacts=self.artifacts,
            metadata=self._build_metadata(
                elapsed_seconds=elapsed_seconds,
                hosts_discovered=len(self.hosts),
                findings_count=len(findings),
                partial_result=True,
                interrupted_stage=stage,
            ),
        )

    def _run_tcp_port_stage(self, hosts: list[HostInfo]) -> None:
        self.current_stage = "tcp_port_scan"
        LOGGER.info(
            "Starting TCP port scan stage for %s hosts using batches of %s.",
            len(hosts),
            self._effective_host_batch_size(),
        )
        batches = _chunked(
            [host.ip for host in hosts],
            self._effective_host_batch_size(),
        )
        host_map = {host.ip: host for host in hosts}
        with ThreadPoolExecutor(max_workers=self._effective_max_workers()) as executor:
            futures = {
                executor.submit(
                    scan_ports_batch,
                    self.runner,
                    batch,
                    self._require_profile(),
                    output_xml_path=self._artifact_file(
                        "tcp",
                        f"tcp-batch-{index:02d}.xml",
                    ),
                ): batch
                for index, batch in enumerate(batches, start=1)
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
                        "TCP port scan finished for %s with %s ports.",
                        host.ip,
                        len(host.ports),
                    )
        for index in range(1, len(batches) + 1):
            artifact = self._artifact_file("tcp", f"tcp-batch-{index:02d}.xml")
            if artifact is not None and Path(artifact).exists():
                self._record_artifact("nmap_xml", artifact, "tcp_port_scan")

    def _run_udp_port_stage(self, hosts: list[HostInfo]) -> None:
        profile = self._require_profile()
        if not profile.udp_ports:
            return

        self.current_stage = "udp_port_scan"
        eligible_hosts = list(hosts)
        if not eligible_hosts:
            return
        LOGGER.info(
            "Starting selective UDP stage for %s hosts across %s ports.",
            len(eligible_hosts),
            len(profile.udp_ports),
        )
        batches = _chunked(
            [host.ip for host in eligible_hosts],
            self._effective_host_batch_size(),
        )
        host_map = {host.ip: host for host in eligible_hosts}
        with ThreadPoolExecutor(max_workers=self._effective_max_workers()) as executor:
            futures = {
                executor.submit(
                    scan_udp_ports_batch,
                    self.runner,
                    batch,
                    profile.udp_ports,
                    output_xml_path=self._artifact_file(
                        "udp",
                        f"udp-batch-{index:02d}.xml",
                    ),
                ): batch
                for index, batch in enumerate(batches, start=1)
            }
            for future in as_completed(futures):
                batch = futures[future]
                results = future.result()
                for ip in batch:
                    host = host_map[ip]
                    host.ports = _merge_ports(
                        host.ports,
                        sorted(
                            results.get(ip, []),
                            key=lambda port: (port.port, port.protocol),
                        ),
                    )
        for index in range(1, len(batches) + 1):
            artifact = self._artifact_file("udp", f"udp-batch-{index:02d}.xml")
            if artifact is not None and Path(artifact).exists():
                self._record_artifact("nmap_xml", artifact, "udp_port_scan")

    def _run_service_stage(self, hosts: list[HostInfo]) -> None:
        self.current_stage = "service_detection"
        eligible_hosts = [host for host in hosts if host.open_ports]
        LOGGER.info(
            "Starting service detection stage for %s hosts with open ports.",
            len(eligible_hosts),
        )
        with ThreadPoolExecutor(max_workers=self._effective_max_workers()) as executor:
            futures = {
                executor.submit(
                    detect_services,
                    self.runner,
                    host.ip,
                    host.ports,
                    self._require_profile(),
                    output_xml_path=self._artifact_file(
                        "services",
                        f"{_safe_host_label(host.ip)}-services.xml",
                    ),
                ): host
                for host in eligible_hosts
            }
            for future in as_completed(futures):
                host = futures[future]
                host.ports = _merge_ports(host.ports, future.result())
                artifact = self._artifact_file(
                    "services",
                    f"{_safe_host_label(host.ip)}-services.xml",
                )
                if artifact is not None and Path(artifact).exists():
                    self._record_artifact(
                        "nmap_xml",
                        artifact,
                        "service_detection",
                        host.ip,
                    )

    def _run_nse_stage(self, hosts: list[HostInfo]) -> None:
        self.current_stage = "nse"
        eligible_hosts = [host for host in hosts if host.open_ports]
        LOGGER.info(
            "Starting NSE stage for %s hosts with open ports.",
            len(eligible_hosts),
        )
        with ThreadPoolExecutor(max_workers=self._effective_max_workers()) as executor:
            futures = {
                executor.submit(
                    run_targeted_nse_scan,
                    self.runner,
                    host.ip,
                    host.ports,
                    scripts=scripts_for_host(
                        host.open_ports,
                        vulners_script=self.settings.vulners_script,
                    ),
                    min_cvss=self.settings.min_cvss,
                    output_xml_path=self._artifact_file(
                        "nse",
                        f"{_safe_host_label(host.ip)}-nse.xml",
                    ),
                    output_text_path=self._artifact_file(
                        "nse",
                        f"{_safe_host_label(host.ip)}-nse.txt",
                    ),
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
                xml_artifact = self._artifact_file(
                    "nse",
                    f"{_safe_host_label(host.ip)}-nse.xml",
                )
                if xml_artifact is not None and Path(xml_artifact).exists():
                    self._record_artifact("nmap_xml", xml_artifact, "nse", host.ip)
                text_artifact = self._artifact_file(
                    "nse",
                    f"{_safe_host_label(host.ip)}-nse.txt",
                )
                if text_artifact is not None and Path(text_artifact).exists():
                    self._record_artifact("nse_output", text_artifact, "nse", host.ip)
                LOGGER.info(
                    "NSE finished for %s with %s open ports and %s host scripts.",
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
                    cpes=port.service.cpes,
                )
                for port in sorted(
                    host.ports,
                    key=lambda item: (item.port, item.protocol),
                )
            ],
        )

    def _nmap_arguments_summary(self) -> str:
        profile = self._require_profile()
        port_stage = (
            "-p- --min-rate 1000 -sS"
            if profile.full_tcp
            else f"--top-ports {profile.top_ports} -sS"
        )
        discovery_stage = " ".join(
            discovery_arguments_for(
                self.scan_target,
                target_mode=self.target_mode,
                local_subnet=self.network_info.subnet if self.network_info else None,
            )[:-1]
        )
        return (
            f"discovery={discovery_stage}; tcp={port_stage}; "
            f"udp={','.join(str(port) for port in profile.udp_ports) or 'disabled'}; "
            f"service=-sV --version-intensity {profile.version_intensity}; "
            f"min_cvss={self.settings.min_cvss}; "
            f"profile={profile.name}; "
            f"workers={self._effective_max_workers()}; "
            f"host_batch_size={self._effective_host_batch_size()}"
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
            "scan_profile": self.settings.scan_profile,
            "target_mode": self.target_mode,
            "max_workers": self._effective_max_workers(),
            "host_batch_size": self._effective_host_batch_size(),
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

    def _resolve_scan_target(self) -> str:
        if self.target_mode == "subnet":
            return self.settings.scan_subnet or self._resolve_network_info().subnet
        return (self.settings.scan_target or "").strip()

    def _effective_max_workers(self) -> int:
        profile = self._require_profile()
        return max(1, min(self.settings.max_workers, profile.max_workers))

    def _effective_host_batch_size(self) -> int:
        profile = self._require_profile()
        return max(1, min(self.settings.host_batch_size, profile.host_batch_size))

    def _require_profile(self) -> ScanProfile:
        if self.profile is None:
            self.profile = resolve_scan_profile(self.settings.scan_profile)
        return self.profile

    def _artifact_file(self, stage: str, filename: str) -> str | None:
        if not self.settings.save_raw_artifacts:
            return None
        return str(Path(self.settings.raw_artifacts_dir) / stage / filename)

    def _record_artifact(
        self,
        kind: str,
        path: str,
        stage: str,
        host_ip: str | None = None,
    ) -> None:
        artifact = ArtifactPayload(
            kind=kind,  # type: ignore[arg-type]
            path=path,
            stage=stage,
            host_ip=host_ip,
        )
        if artifact not in self.artifacts:
            self.artifacts.append(artifact)


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
        items[index : index + chunk_size] for index in range(0, len(items), chunk_size)
    ]


def _safe_host_label(ip: str) -> str:
    return ip.replace(".", "-")
