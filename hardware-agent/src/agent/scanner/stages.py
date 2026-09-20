from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, TypeVar

from agent.assessment.policy import MachineType
from agent.config import (
    NSPI_HOST_TIMEOUT,
    NSPI_SCRIPT_TIMEOUT,
    deep_stage_scripts,
    effective_version_intensity,
    subprocess_timeout_for,
)
from agent.discovery.port_discovery import (
    NSPI_PASS1_ARGS,
    NSPI_PASS2_ARGS,
    discovery_arguments,
    merge_ports,
    scan_ports_batch,
)
from agent.discovery.service_detection import detect_services
from agent.discovery.vulnerability_detection import run_nse_vulnerability_scan
from agent.normalize.contracts import (
    DeviceProfilePayload,
    HostPayload,
    ModbusAddressRangePayload,
    ModbusDeviceIdentificationPayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    OperatingSystemDetection,
    PortPayload,
)
from agent.ot.digest import load_digest_key
from agent.ot.modbus.fingerprints import correlate_fc43_fingerprints
from agent.ot.modbus.inventory import has_modbus_candidate, inventory_modbus_host
from agent.ot.modbus.mapper import MappingBudget, map_modbus_service
from agent.ot.policy import (
    MAX_OT_HOST_SECONDS,
    MAX_OT_STAGE_SECONDS,
    OtAutomationPolicy,
    min_not_none,
)
from agent.scanner.errors import (
    BudgetExceeded,
    CircuitBreakerError,
    TransientScanError,
    UnitScanError,
)
from agent.scanner.nmap import AGENT_VERSION, LoggedNmapRunner
from agent.scanner.progress import ScanEvent

if TYPE_CHECKING:
    from agent.config import AgentSettings
    from agent.ot.modbus.client import ModbusClientController
    from agent.scanner.models import HostInfo
    from agent.scanner.nmap import NmapRunner
    from agent.scanner.progress import ScanReporter
    from agent.targeted.models import TargetedStageSummary
    from agent.utils.network import LocalNetworkInfo

LOGGER = logging.getLogger(__name__)

_UnitResult = TypeVar("_UnitResult")


def _run_unit_with_retry(
    retries: int,
    work: Callable[..., _UnitResult],
    *args: object,
    **kwargs: object,
) -> _UnitResult:
    last_exc: TransientScanError | None = None
    for _ in range(retries + 1):
        try:
            return work(*args, **kwargs)
        except TransientScanError as exc:
            last_exc = exc
    raise UnitScanError(str(last_exc)) from last_exc


def set_runner_stage(runner: NmapRunner, stage: str) -> None:
    if isinstance(runner, LoggedNmapRunner):
        runner.set_stage(stage)


def _emit(reporter: ScanReporter | None, event: ScanEvent) -> None:
    if reporter is not None:
        reporter.emit(event)


def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    return [
        items[index : index + chunk_size] for index in range(0, len(items), chunk_size)
    ]


def _recover_deep_stage_services(
    runner: NmapRunner,
    settings: AgentSettings,
    host: HostInfo,
) -> bool:
    try:
        recovered = detect_services(
            runner,
            host.ip,
            host.ports,
            version_intensity=effective_version_intensity(settings.version_intensity),
            timeout=subprocess_timeout_for(settings.scan_mode, "nse"),
        )
    except (BudgetExceeded, UnitScanError, TransientScanError) as exc:
        LOGGER.warning("Service recovery failed for %s: %s", host.ip, exc)
        return False
    if not recovered:
        return False
    host.ports = merge_ports(host.ports, recovered)
    return True


def run_port_stage(
    runner: NmapRunner,
    settings: AgentSettings,
    hosts: list[HostInfo],
    reporter: ScanReporter | None = None,
    cancel_event: threading.Event | None = None,
) -> int:
    set_runner_stage(runner, "ports")
    LOGGER.info(
        "Starting port scan stage for %s hosts using batches of %s.",
        len(hosts),
        settings.host_batch_size,
    )
    batches = _chunked([host.ip for host in hosts], settings.host_batch_size)
    host_map = {host.ip: host for host in hosts}
    started_message = (
        "Scanning all ports…"
        if settings.scan_mode in {"extensive", "max"}
        else "Scanning ports…"
    )
    _emit(reporter, ScanEvent(kind="port_stage_started", message=started_message))
    batches_total = len(batches)
    batches_done = 0
    hosts_skipped = 0
    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {
            executor.submit(
                _run_unit_with_retry,
                settings.transient_retries,
                scan_ports_batch,
                runner,
                batch,
                settings.scan_mode,
                timeout=subprocess_timeout_for(settings.scan_mode, "ports"),
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            if cancel_event is not None and cancel_event.is_set():
                break
            batch = futures[future]
            try:
                results = future.result()
            except CircuitBreakerError:
                raise
            except BudgetExceeded:
                hosts_skipped += len(batch)
                for ip in batch:
                    _emit(reporter, ScanEvent(kind="unit_timed_out", ip=ip))
                LOGGER.warning("Port scan timed out for batch %s.", batch)
            except UnitScanError:
                hosts_skipped += len(batch)
                for ip in batch:
                    _emit(reporter, ScanEvent(kind="unit_failed", ip=ip))
                LOGGER.warning("Port scan failed for batch %s.", batch)
            else:
                for ip in batch:
                    host = host_map[ip]
                    result = results.get(ip)
                    if result is None:
                        raise UnitScanError(
                            f"Port scan did not return results for {ip}"
                        )
                    host.ports = sorted(
                        result.ports,
                        key=lambda port: (port.port, port.protocol),
                    )
                    host.operating_system = result.operating_system
                    if result.skipped:
                        hosts_skipped += 1
                        _emit(reporter, ScanEvent(kind="unit_timed_out", ip=ip))
                        LOGGER.warning(
                            "Port scan hit the host timeout for %s; "
                            "partial evidence kept.",
                            ip,
                        )
                    LOGGER.info(
                        "Port scan finished for %s with %s ports.",
                        host.ip,
                        len(host.ports),
                    )
            batches_done += 1
            _emit(
                reporter,
                ScanEvent(
                    kind="port_batch_done",
                    batches_done=batches_done,
                    batches_total=batches_total,
                ),
            )
            if hosts and hosts_skipped / len(hosts) > settings.unit_failure_threshold:
                raise CircuitBreakerError(
                    f"Port stage aborted: {hosts_skipped}/{len(hosts)} units failed"
                )
    ports_open = sum(len(host.ports) for host in hosts)
    _emit(
        reporter,
        ScanEvent(
            kind="port_stage_done",
            message=f"{ports_open} open ports found",
            ports_open=ports_open,
            units_skipped=hosts_skipped,
            units_total=len(hosts),
        ),
    )
    return hosts_skipped


def run_deep_inspection_stage(
    runner: NmapRunner,
    settings: AgentSettings,
    hosts: list[HostInfo],
    reporter: ScanReporter | None = None,
    cancel_event: threading.Event | None = None,
) -> int:
    set_runner_stage(runner, "nse")
    eligible_hosts = [host for host in hosts if host.open_ports]
    LOGGER.info(
        "Starting deep inspection stage for %s hosts with open ports.",
        len(eligible_hosts),
    )
    hosts_total = len(eligible_hosts)
    started_message = (
        "Running scripts…" if hosts_total else "No hosts to inspect — skipping scripts"
    )
    _emit(
        reporter,
        ScanEvent(
            kind="deep_stage_started",
            message=started_message,
            hosts_total=hosts_total,
        ),
    )
    hosts_done = 0
    hosts_skipped = 0
    nspi_options = (
        {
            "script_timeout": NSPI_SCRIPT_TIMEOUT,
            "host_timeout": NSPI_HOST_TIMEOUT,
            "detect_os": True,
        }
        if settings.scan_mode == "nspi"
        else {}
    )
    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {
            executor.submit(
                _run_unit_with_retry,
                settings.transient_retries,
                run_nse_vulnerability_scan,
                runner,
                host.ip,
                host.ports,
                version_intensity=effective_version_intensity(
                    settings.version_intensity
                ),
                scripts=deep_stage_scripts(settings.scan_mode),
                min_cvss=settings.min_cvss,
                timeout=subprocess_timeout_for(settings.scan_mode, "nse"),
                **nspi_options,
            ): host
            for host in eligible_hosts
        }
        for future in as_completed(futures):
            if cancel_event is not None and cancel_event.is_set():
                break
            host = futures[future]
            try:
                result = future.result()
            except CircuitBreakerError:
                raise
            except BudgetExceeded:
                LOGGER.warning("Deep inspection timed out for %s.", host.ip)
                if _recover_deep_stage_services(runner, settings, host):
                    LOGGER.info(
                        "Deep inspection recovered service evidence for %s.",
                        host.ip,
                    )
                else:
                    hosts_skipped += 1
                    _emit(reporter, ScanEvent(kind="unit_timed_out", ip=host.ip))
                    LOGGER.warning(
                        "Deep inspection service recovery found nothing for %s.",
                        host.ip,
                    )
            except UnitScanError:
                LOGGER.warning("Deep inspection failed for %s.", host.ip)
                if _recover_deep_stage_services(runner, settings, host):
                    LOGGER.info(
                        "Deep inspection recovered service evidence for %s.",
                        host.ip,
                    )
                else:
                    hosts_skipped += 1
                    _emit(reporter, ScanEvent(kind="unit_failed", ip=host.ip))
                    LOGGER.warning(
                        "Deep inspection service recovery found nothing for %s.",
                        host.ip,
                    )
            else:
                if result is None:
                    if settings.scan_mode == "nspi":
                        LOGGER.warning(
                            "Deep inspection hit the host timeout for %s.", host.ip
                        )
                    else:
                        LOGGER.warning(
                            "Deep inspection returned no result for %s.", host.ip
                        )
                    if _recover_deep_stage_services(runner, settings, host):
                        LOGGER.info(
                            "Deep inspection recovered service evidence for %s.",
                            host.ip,
                        )
                    else:
                        hosts_skipped += 1
                        if settings.scan_mode == "nspi":
                            _emit(
                                reporter,
                                ScanEvent(kind="unit_timed_out", ip=host.ip),
                            )
                        else:
                            _emit(reporter, ScanEvent(kind="unit_failed", ip=host.ip))
                        LOGGER.warning(
                            "Deep inspection service recovery found nothing for %s.",
                            host.ip,
                        )
                else:
                    host.ports = merge_ports(host.ports, result.ports)
                    host.host_scripts = result.host_scripts
                    if (
                        settings.scan_mode == "nspi"
                        and result.operating_system is not None
                        and (
                            host.operating_system is None
                            or result.operating_system.accuracy
                            > host.operating_system.accuracy
                        )
                    ):
                        host.operating_system = result.operating_system
                    LOGGER.info(
                        "Deep inspection finished for %s with %s open ports "
                        "and %s host scripts.",
                        host.ip,
                        len(host.open_ports),
                        len(host.host_scripts),
                    )
            hosts_done += 1
            _emit(
                reporter,
                ScanEvent(
                    kind="host_inspected",
                    message=f"Scanned {host.ip} ({hosts_done}/{hosts_total})",
                    hosts_done=hosts_done,
                    hosts_total=hosts_total,
                    ip=host.ip,
                ),
            )
            if (
                hosts_total
                and hosts_skipped / hosts_total > settings.unit_failure_threshold
            ):
                raise CircuitBreakerError(
                    f"Deep inspection aborted: {hosts_skipped}/{hosts_total} "
                    "units failed"
                )
    _emit(
        reporter,
        ScanEvent(
            kind="deep_stage_done",
            message="Deep inspection complete",
            units_skipped=hosts_skipped,
            units_total=hosts_total,
        ),
    )
    return hosts_skipped


@dataclass(frozen=True, slots=True)
class OtInspectionResult:
    stage_deadline_reached: bool = False
    stage_deadline_seconds: int | None = None


def _elapsed_stage_seconds(stage_deadline: float, stage_started: float) -> int:
    return max(1, int(round(stage_deadline - stage_started)))


def _stage_deadline_hit(
    stage_deadline: float | None,
    stage_started: float,
) -> int | None:
    if stage_deadline is None or perf_counter() < stage_deadline:
        return None
    return _elapsed_stage_seconds(stage_deadline, stage_started)


def run_ot_inspection_stage(
    settings: AgentSettings,
    hosts: list[HostInfo],
    reporter: ScanReporter | None = None,
    cancel_event: threading.Event | None = None,
    modbus_controller: ModbusClientController | None = None,
    policy: OtAutomationPolicy | None = None,
    deadline: float | None = None,
) -> OtInspectionResult:
    """Run serial, bounded OT enrichment after the existing NSE stage."""

    if settings.scan_mode != "nspi":
        return OtInspectionResult()

    eligible_hosts = [host for host in hosts if has_modbus_candidate(host)]
    hosts_total = len(eligible_hosts)
    action = (
        "Mapping Modbus read-only ranges..."
        if settings.nspi_submode == "read_only_mapping"
        else "Inventorying Modbus devices..."
    )
    _emit(
        reporter,
        ScanEvent(
            kind="ot_stage_started",
            message=action if hosts_total else "No Modbus candidates found",
            hosts_total=hosts_total,
        ),
    )
    hosts_done = 0
    deadline_seconds: int | None = None
    effective_policy = policy or OtAutomationPolicy()
    digest_key = load_digest_key()
    stage_started = perf_counter()
    stage_deadline = min_not_none(deadline, stage_started + MAX_OT_STAGE_SECONDS)
    for host in eligible_hosts:
        if cancel_event is not None and cancel_event.is_set():
            break
        if _stage_deadline_hit(stage_deadline, stage_started) is not None:
            break
        host_deadline = min_not_none(
            stage_deadline,
            perf_counter() + MAX_OT_HOST_SECONDS,
        )
        host.industrial_services = inventory_modbus_host(
            host,
            policy=effective_policy,
            cancel_event=cancel_event,
            controller=modbus_controller,
            deadline=host_deadline,
        )
        if settings.nspi_submode == "read_only_mapping":
            budget = MappingBudget(
                maximum=effective_policy.max_mapping_requests_per_host,
                used=sum(service.requests_sent for service in host.industrial_services),
            )
            for service in host.industrial_services:
                map_modbus_service(
                    host,
                    service,
                    policy=effective_policy,
                    cancel_event=cancel_event,
                    controller=modbus_controller,
                    deadline=host_deadline,
                    budget=budget,
                    digest_key=digest_key,
                )
        correlate_fc43_fingerprints(host)
        hosts_done += 1
        _emit(
            reporter,
            ScanEvent(
                kind="modbus_host_inspected",
                message=(
                    f"Mapped Modbus on {host.ip}"
                    if settings.nspi_submode == "read_only_mapping"
                    else f"Inventoried Modbus on {host.ip}"
                ),
                hosts_done=hosts_done,
                hosts_total=hosts_total,
                ip=host.ip,
            ),
        )
    cancelled = cancel_event is not None and cancel_event.is_set()
    if not cancelled:
        deadline_seconds = _stage_deadline_hit(stage_deadline, stage_started)
        if deadline_seconds is not None:
            reason = f"Time limit reached during Modbus inventory ({deadline_seconds}s)"
            _emit(
                reporter,
                ScanEvent(
                    kind="ot_stage_deadline",
                    message=reason,
                    units_skipped=hosts_total - hosts_done,
                    units_total=hosts_total,
                    deadline_seconds=deadline_seconds,
                ),
            )
    result = OtInspectionResult(
        stage_deadline_reached=deadline_seconds is not None,
        stage_deadline_seconds=deadline_seconds,
    )
    _emit(
        reporter,
        ScanEvent(
            kind="ot_stage_done",
            message=(
                "Modbus read-only mapping complete"
                if settings.nspi_submode == "read_only_mapping"
                else "Modbus inventory complete"
            ),
            units_total=hosts_total,
            units_skipped=hosts_total - hosts_done,
        ),
    )
    return result


def build_host_payload(
    host: HostInfo,
    *,
    machine_type: MachineType | None = None,
    device_profile: DeviceProfilePayload | None = None,
) -> HostPayload:
    return HostPayload(
        ip=host.ip,
        mac=host.mac,
        hostname=host.hostname or host.ip,
        vendor=host.vendor or "unknown",
        operating_system=(
            OperatingSystemDetection(
                name=host.operating_system.name,
                accuracy=host.operating_system.accuracy,
                vendor=host.operating_system.vendor,
                family=host.operating_system.family,
                generation=host.operating_system.generation,
                device_type=host.operating_system.device_type,
                cpes=host.operating_system.cpes,
            )
            if host.operating_system is not None
            else None
        ),
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
                cpes=sorted(set(port.service.cpes)),
            )
            for port in sorted(
                host.ports,
                key=lambda item: (item.port, item.protocol),
            )
        ],
        industrial_services=[
            ModbusTcpServicePayload(
                port=service.port,
                confidence=service.confidence,
                evidence_sources=service.evidence_sources,
                mapping_source=service.mapping_source,
                write_requests_sent=service.write_requests_sent,
                units=[
                    ModbusUnitPayload(
                        unit_id=unit.unit_id,
                        status=unit.status,
                        exception_code=unit.exception_code,
                        error=unit.error,
                        device_identification=(
                            ModbusDeviceIdentificationPayload(
                                vendor_name=unit.device_identification.vendor_name,
                                product_code=unit.device_identification.product_code,
                                major_minor_revision=(
                                    unit.device_identification.major_minor_revision
                                ),
                                vendor_url=unit.device_identification.vendor_url,
                                product_name=unit.device_identification.product_name,
                                model_name=unit.device_identification.model_name,
                                user_application_name=(
                                    unit.device_identification.user_application_name
                                ),
                                objects=unit.device_identification.objects,
                                truncated=unit.device_identification.truncated,
                            )
                            if unit.device_identification is not None
                            else None
                        ),
                        identification_sources=unit.identification_sources,
                        address_ranges=[
                            ModbusAddressRangePayload(
                                address_space=item.address_space,
                                start_address=item.start_address,
                                count=item.count,
                                status=item.status,
                                exception_code=item.exception_code,
                                label=item.label,
                                value_digest=item.value_digest,
                                observed_at=item.observed_at,
                            )
                            for item in unit.address_ranges
                        ],
                    )
                    for unit in service.units
                ],
            )
            for service in host.industrial_services
        ],
        machine_type=machine_type,
        device_profile=device_profile,
    )


def nmap_arguments_summary(settings: AgentSettings) -> str:
    if settings.scan_mode == "nspi":
        port_stage = (
            f"pass1:{' '.join(NSPI_PASS1_ARGS)} (top-1000); "
            f"pass2:{' '.join(NSPI_PASS2_ARGS)}"
        )
    else:
        port_stage = f"-Pn -n -T4 {' '.join(discovery_arguments(settings.scan_mode))}"
    deep_scripts = deep_stage_scripts(settings.scan_mode)
    ot_inspection = (
        settings.nspi_submode if settings.scan_mode == "nspi" else "disabled"
    )
    version_intensity = effective_version_intensity(settings.version_intensity)
    deep_inspection = f"-Pn -n -T4 -sV --version-intensity {version_intensity}"
    if settings.scan_mode == "nspi":
        deep_inspection += (
            f" -O --script-timeout {NSPI_SCRIPT_TIMEOUT}"
            f" --host-timeout {NSPI_HOST_TIMEOUT}"
        )
    return (
        f"discovery=-sn -PE -T4; ports={port_stage}; "
        f"deep_inspection={deep_inspection}; "
        "scripts="
        f"{','.join(deep_scripts)}; "
        f"min_cvss={settings.min_cvss}; "
        f"ot_inspection={ot_inspection}; "
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
    hosts: list[HostInfo] | None = None,
    partial_result: bool = False,
    interrupted_stage: str | None = None,
    terminated_by: str | None = None,
    ot_inspection: OtInspectionResult | None = None,
    targeted_summary: TargetedStageSummary | None = None,
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
    if terminated_by is not None:
        metadata["terminated_by"] = terminated_by
    if settings.scan_mode == "nspi":
        modbus_services = [
            service for host in hosts or [] for service in host.industrial_services
        ]
        digest_key = load_digest_key()
        metadata.update(
            {
                "nspi_policy_version": 1,
                "nspi_submode": settings.nspi_submode,
                "modbus_candidates": len(modbus_services),
                "modbus_confirmed": sum(
                    service.confidence == "confirmed" for service in modbus_services
                ),
                "modbus_units": sum(len(service.units) for service in modbus_services),
                "modbus_requests_sent": sum(
                    service.requests_sent for service in modbus_services
                ),
                "modbus_timeouts": sum(service.timeouts for service in modbus_services),
                "modbus_mapping_requests_sent": sum(
                    service.mapping_requests_sent for service in modbus_services
                ),
                "modbus_mapping_ranges_readable": sum(
                    item.status == "readable"
                    for service in modbus_services
                    for unit in service.units
                    for item in unit.address_ranges
                ),
                "modbus_mapping_ranges_skipped": sum(
                    service.mapping_ranges_skipped for service in modbus_services
                ),
                "modbus_cpe_candidates": sum(
                    "fc43-fingerprint-catalog" in service.evidence_sources
                    for service in modbus_services
                ),
                "modbus_write_requests_sent": sum(
                    service.write_requests_sent for service in modbus_services
                ),
                "modbus_parse_failures": sum(
                    service.parse_failures for service in modbus_services
                ),
                "modbus_digest_key_present": digest_key is not None,
            }
        )
        ot_result = ot_inspection or OtInspectionResult()
        if ot_result.stage_deadline_reached:
            metadata["modbus_stage_deadline_reached"] = True
            if ot_result.stage_deadline_seconds is not None:
                metadata["modbus_stage_deadline_seconds"] = (
                    ot_result.stage_deadline_seconds
                )
    if targeted_summary is not None:
        metadata.update(
            {
                "targeted_units_eligible": targeted_summary.eligible,
                "targeted_units_planned": targeted_summary.planned,
                "targeted_units_omitted": targeted_summary.omitted,
                "targeted_units_completed": targeted_summary.completed,
                "targeted_units_failed": targeted_summary.failed,
                "targeted_units_timed_out": targeted_summary.timed_out,
                "targeted_units_skipped": targeted_summary.skipped,
                "targeted_finding_candidates": targeted_summary.finding_candidates,
                "targeted_observation_candidates": (
                    targeted_summary.observation_candidates
                ),
                "targeted_coverage": _targeted_coverage(targeted_summary),
            }
        )
    return metadata


def _targeted_coverage(summary: TargetedStageSummary) -> str:
    """Render the bounded, deterministic per-tool coverage summary."""

    from agent.config import TARGETED_COVERAGE_LIMIT_CHARS
    from agent.targeted.models import TargetedGapReason, TargetedOutcome, TargetedTool

    chunks: list[str] = []
    for tool in TargetedTool:
        counts = summary.per_tool[tool]
        chunk = (
            f"{tool.value}:c={counts[TargetedOutcome.COMPLETED]},"
            f"f={counts[TargetedOutcome.FAILED]},"
            f"t={counts[TargetedOutcome.TIMED_OUT]},"
            f"s={counts[TargetedOutcome.SKIPPED]}"
        )
        gaps = [
            f"{reason.value}:{summary.gap_by_tool[tool][reason]}"
            for reason in TargetedGapReason
            if summary.gap_by_tool[tool][reason]
        ]
        if gaps:
            chunk += ",gaps=" + "|".join(gaps)
        chunks.append(chunk)
    return ";".join(chunks)[:TARGETED_COVERAGE_LIMIT_CHARS]
