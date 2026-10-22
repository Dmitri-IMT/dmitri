from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from time import perf_counter
from typing import TYPE_CHECKING, Literal, TypeVar

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
    OpcUaTcpServicePayload,
    OperatingSystemDetection,
    PortPayload,
)
from agent.ot.digest import load_digest_key
from agent.ot.modbus.fingerprints import correlate_fc43_fingerprints
from agent.ot.modbus.inventory import has_modbus_candidate, inventory_modbus_host
from agent.ot.modbus.mapper import MappingBudget, map_modbus_service
from agent.ot.opcua.client import OpcUaClient
from agent.ot.opcua.inventory import inventory_opcua_service
from agent.ot.opcua.mapper import map_opcua_service
from agent.ot.opcua.models import OpcUaInventory
from agent.ot.policy import (
    MAX_OT_HOST_SECONDS,
    MAX_OT_STAGE_SECONDS,
    OtAutomationPolicy,
    min_not_none,
    must_stop,
)
from agent.scanner.errors import (
    BudgetExceeded,
    CircuitBreakerError,
    TransientScanError,
    UnitScanError,
)
from agent.scanner.models import StageCoverage
from agent.scanner.nmap import LoggedNmapRunner
from agent.scanner.progress import ScanEvent
from agent.version import installed_version

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
                    host_map[ip].stage_coverage.append(
                        StageCoverage(
                            "ports", "timed_out", "nmap_ports", "port_timeout"
                        )
                    )
                    _emit(reporter, ScanEvent(kind="unit_timed_out", ip=ip))
                LOGGER.warning("Port scan timed out for batch %s.", batch)
            except UnitScanError:
                hosts_skipped += len(batch)
                for ip in batch:
                    host_map[ip].stage_coverage.append(
                        StageCoverage("ports", "failed", "nmap_ports", "port_failed")
                    )
                    _emit(reporter, ScanEvent(kind="unit_failed", ip=ip))
                LOGGER.warning("Port scan failed for batch %s.", batch)
            else:
                for ip in batch:
                    host = host_map[ip]
                    result = results.get(ip)
                    if result is None:
                        hosts_skipped += 1
                        host.stage_coverage.append(
                            StageCoverage(
                                "ports", "failed", "nmap_ports", "port_no_result"
                            )
                        )
                        _emit(reporter, ScanEvent(kind="unit_failed", ip=ip))
                        LOGGER.warning("Port scan returned no result for %s.", ip)
                        continue
                    host.ports = sorted(
                        result.ports,
                        key=lambda port: (port.port, port.protocol),
                    )
                    host.identity = host.identity.merged_with(result.identity)
                    host.operating_system = result.operating_system
                    if result.skipped:
                        hosts_skipped += 1
                        host.stage_coverage.append(
                            StageCoverage(
                                "ports", "partial", "nmap_ports", "port_host_timeout"
                            )
                        )
                        _emit(reporter, ScanEvent(kind="unit_timed_out", ip=ip))
                        LOGGER.warning(
                            "Port scan hit the host timeout for %s; "
                            "partial evidence kept.",
                            ip,
                        )
                    else:
                        host.stage_coverage.append(
                            StageCoverage("ports", "completed", "nmap_ports")
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
    ports_open = sum(len(host.open_ports) for host in hosts)
    ports_filtered = sum(
        1 for host in hosts for port in host.ports if port.state == "filtered"
    )
    _emit(
        reporter,
        ScanEvent(
            kind="port_stage_done",
            message=f"{ports_open} open ports found",
            ports_open=ports_open,
            ports_filtered=ports_filtered,
            units_skipped=hosts_skipped,
            units_total=len(hosts),
        ),
    )
    return hosts_skipped


def _record_deep_gap(
    runner: NmapRunner,
    settings: AgentSettings,
    host: HostInfo,
    reporter: ScanReporter | None,
    outcome: Literal["failed", "timed_out"],
    reason: str,
) -> bool:
    recovered = _recover_deep_stage_services(runner, settings, host)
    host.stage_coverage.append(
        StageCoverage(
            "deep_inspection",
            "partial" if recovered else outcome,
            "service_recovery" if recovered else "port_discovery",
            reason,
        )
    )
    if recovered:
        LOGGER.info("Deep inspection recovered service evidence for %s.", host.ip)
    else:
        kind = "unit_timed_out" if outcome == "timed_out" else "unit_failed"
        _emit(reporter, ScanEvent(kind=kind, ip=host.ip))
        LOGGER.warning(
            "Deep inspection service recovery found nothing for %s.", host.ip
        )
    return recovered


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
    hosts_incomplete = 0
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
                hosts_incomplete += 1
                if not _record_deep_gap(
                    runner, settings, host, reporter, "timed_out", "nse_timeout"
                ):
                    hosts_skipped += 1
            except UnitScanError:
                LOGGER.warning("Deep inspection failed for %s.", host.ip)
                hosts_incomplete += 1
                if not _record_deep_gap(
                    runner, settings, host, reporter, "failed", "nse_failed"
                ):
                    hosts_skipped += 1
            else:
                if result is None:
                    if settings.scan_mode == "nspi":
                        LOGGER.warning(
                            "Deep inspection hit the host timeout for %s.", host.ip
                        )
                        outcome, reason = "timed_out", "nse_timeout"
                    else:
                        LOGGER.warning(
                            "Deep inspection returned no result for %s.", host.ip
                        )
                        outcome, reason = "failed", "nse_no_result"
                    hosts_incomplete += 1
                    if not _record_deep_gap(
                        runner, settings, host, reporter, outcome, reason
                    ):
                        hosts_skipped += 1
                else:
                    host.stage_coverage.append(
                        StageCoverage("deep_inspection", "completed", "nmap_nse")
                    )
                    host.ports = merge_ports(host.ports, result.ports)
                    host.host_scripts = result.host_scripts
                    host.identity = host.identity.merged_with(result.identity)
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
    return hosts_incomplete


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


def _protocol_coverage(
    statuses,
    cancel_event,
    host_deadline,
    source,
    *,
    port=None,
    protocol=None,
    tool=None,
):
    coverage = ("ot_inspection", source, port, protocol, tool)

    def record(outcome, reason=None):
        return StageCoverage(
            coverage[0], outcome, coverage[1], reason,
            coverage[2], coverage[3], coverage[4]
        )

    outcomes = set(statuses)
    if cancel_event is not None and cancel_event.is_set() and outcomes - {"completed"}:
        return record("partial", "scan_cancelled")
    if "failed" in outcomes:
        outcome = "partial" if len(outcomes) > 1 else "failed"
        return record(outcome, "service_error")
    if "timed_out" in outcomes:
        return record("partial", "timeout")
    if "skipped" in outcomes:
        return record("partial", "service_skipped")
    if (
        host_deadline is not None
        and perf_counter() >= host_deadline
        and outcomes - {"completed"}
    ):
        return record("partial", "ot_host_deadline")
    if outcomes & {"partial", "denied", "unsupported_security"}:
        return record("partial", "limited_coverage")
    return record("completed")


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

    eligible_hosts = [
        host
        for host in hosts
        if has_modbus_candidate(host) or has_opcua_candidate(host)
    ]
    hosts_total = len(eligible_hosts)
    action = (
        "Mapping industrial services read-only..."
        if settings.nspi_submode == "read_only_mapping"
        else "Inventorying industrial services..."
    )
    _emit(
        reporter,
        ScanEvent(
            kind="ot_stage_started",
            message=action if hosts_total else "No industrial candidates found",
            hosts_total=hosts_total,
        ),
    )
    hosts_done = 0
    deadline_seconds: int | None = None
    effective_policy = policy or OtAutomationPolicy()
    digest_key = load_digest_key()
    stage_started = perf_counter()
    stage_deadline = min_not_none(deadline, stage_started + MAX_OT_STAGE_SECONDS)
    stopped_at: int | None = None
    host_deadlines: dict[str, float] = {}
    for index, host in enumerate(eligible_hosts):
        if cancel_event is not None and cancel_event.is_set():
            stopped_at = index
            break
        if _stage_deadline_hit(stage_deadline, stage_started) is not None:
            stopped_at = index
            break
        host_deadline = min_not_none(
            stage_deadline,
            perf_counter() + MAX_OT_HOST_SECONDS,
        )
        host_deadlines[host.ip] = host_deadline or (
            perf_counter() + MAX_OT_HOST_SECONDS
        )
        host.industrial_services.extend(
            inventory_modbus_host(
                host,
                policy=effective_policy,
                cancel_event=cancel_event,
                controller=modbus_controller,
                deadline=host_deadline,
                request_budget=min(32, effective_policy.max_mapping_requests_per_host),
            )
        )
        host.opcua_services.extend(
            _inventory_opcua_host(
                host,
                cancel_event=cancel_event,
                deadline=host_deadline,
                request_budget=min(32, effective_policy.max_mapping_requests_per_host),
                pacing_ms=max(100, effective_policy.inter_request_delay_ms),
            )
        )
    # Inventory every candidate before starting either protocol's mapping phase.
    if settings.nspi_submode == "read_only_mapping":
        for host in eligible_hosts:
            host_deadline = host_deadlines.get(host.ip)
            if host_deadline is None:
                continue
            budget = MappingBudget(
                maximum=min(32, effective_policy.max_mapping_requests_per_host),
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
            opcua_budget = MappingBudget(
                maximum=min(32, effective_policy.max_mapping_requests_per_host),
                used=sum(service.requests_sent for service in host.opcua_services),
            )
            for service_index, service in enumerate(host.opcua_services):
                remaining = max(0, opcua_budget.maximum - opcua_budget.used)
                if remaining <= 0 or must_stop(cancel_event, host_deadline):
                    host.opcua_services[service_index] = replace(
                        service,
                        mapping=_opcua_skipped_mapping(
                            "cancelled"
                            if cancel_event and cancel_event.is_set()
                            else "request_budget_exhausted"
                        ),
                    )
                    continue
                mapped = _map_opcua_service(
                    service,
                    host.ip,
                    cancel_event=cancel_event,
                    deadline=host_deadline,
                    request_budget=remaining,
                    pacing_ms=max(100, effective_policy.inter_request_delay_ms),
                )
                host.opcua_services[service_index] = replace(service, mapping=mapped)
                if mapped.request_count_known:
                    opcua_budget.used += _mapping_request_count(mapped)
                else:
                    opcua_budget.used = opcua_budget.maximum
    for host in eligible_hosts:
        if host.ip not in host_deadlines:
            continue
        host_deadline = host_deadlines[host.ip]
        correlate_fc43_fingerprints(host)
        if has_modbus_candidate(host):
            for item in host.industrial_services:
                statuses = ["completed" if item.confidence == "confirmed" else "failed"]
                ranges = [area for unit in item.units for area in unit.address_ranges]
                if item.mapping_ranges_skipped or any(
                    area.status == "skipped" for area in ranges
                ):
                    statuses.append("skipped")
                if any(area.status in {"timeout", "error"} for area in ranges):
                    statuses.append("failed")
                if any(
                    area.status in {"illegal_address", "illegal_function"}
                    for area in ranges
                ):
                    statuses.append("partial")
                host.stage_coverage.append(_protocol_coverage(
                    statuses, cancel_event, host_deadline, "modbus_inspection",
                    port=item.port, protocol="tcp", tool="modbus"))
        if has_opcua_candidate(host):
            for item in host.opcua_services:
                statuses = [item.inventory_status]
                if settings.nspi_submode == "read_only_mapping" and item.mapping:
                    statuses.append(item.mapping.status)
                host.stage_coverage.append(_protocol_coverage(
                    statuses, cancel_event, host_deadline, "opcua_inspection",
                    port=item.port, protocol="tcp", tool="opcua"))
        hosts_done += 1
        _emit(
            reporter,
            ScanEvent(
                kind=(
                    "modbus_host_inspected"
                    if has_modbus_candidate(host)
                    else "industrial_host_inspected"
                ),
                message=f"Inspected industrial services on {host.ip}",
                hosts_done=hosts_done,
                hosts_total=hosts_total,
                ip=host.ip,
            ),
        )
    cancelled = cancel_event is not None and cancel_event.is_set()
    if stopped_at is not None:
        reason = "scan_cancelled" if cancelled else "stage_budget"
        for host in eligible_hosts[stopped_at:]:
            if has_modbus_candidate(host):
                host.stage_coverage.append(
                    StageCoverage(
                        "ot_inspection", "skipped", "modbus_inspection", reason
                    )
                )
            if has_opcua_candidate(host):
                host.stage_coverage.append(
                    StageCoverage(
                        "ot_inspection", "skipped", "opcua_inspection", reason
                    )
                )
    if not cancelled:
        deadline_seconds = _stage_deadline_hit(stage_deadline, stage_started)
        if deadline_seconds is not None:
            reason = (
                f"Time limit reached during industrial inspection ({deadline_seconds}s)"
            )
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
                "Industrial read-only mapping complete"
                if settings.nspi_submode == "read_only_mapping"
                else "Industrial inventory complete"
            ),
            industrial_services=sum(
                len(host.industrial_services) + len(host.opcua_services)
                for host in hosts
            ),
            units_total=hosts_total,
            units_skipped=hosts_total - hosts_done,
        ),
    )
    return result


def has_opcua_candidate(host: HostInfo) -> bool:
    return any(
        port.protocol.lower() == "tcp"
        and (
            port.port == 4840
            or "opcua" in port.service.name.lower()
            or "opcuatcp" in port.service.name.lower()
        )
        for port in host.open_ports
    )


def _inventory_opcua_host(
    host: HostInfo,
    *,
    cancel_event: threading.Event | None,
    deadline: float | None,
    request_budget: int,
    pacing_ms: int = 100,
) -> list[OpcUaInventory]:
    results: list[OpcUaInventory] = []
    candidates = [
        port for port in sorted(host.open_ports, key=lambda item: item.port)
        if port.protocol.lower() == "tcp" and (
            port.port == 4840 or "opcua" in port.service.name.lower()
            or "opcuatcp" in port.service.name.lower()
        )
    ]
    candidates = list({port.port: port for port in candidates}.values())
    active, limited = candidates[:4], candidates[4:]
    if request_budget <= 0:
        from datetime import datetime, timezone

        results.extend(
            OpcUaInventory(
                "opcua_tcp",
                port.port,
                "suspected",
                ("tcp_candidate",),
                "partial",
                datetime.now(timezone.utc),
                reason_code="request_budget_exhausted",
                reason_codes=("request_budget_exhausted",),
            )
            for port in candidates
        )
        return results
    client = OpcUaClient()
    for port in active:
        if must_stop(cancel_event, deadline):
            break
        remaining = max(0.1, min(2.0, (deadline - perf_counter()) if deadline else 2.0))
        try:

            async def collect():
                task = asyncio.create_task(
                    inventory_opcua_service(
                        client,
                        host.ip,
                        port.port,
                        request_budget=min(32, request_budget),
                        timeout=remaining,
                        pacing_ms=pacing_ms,
                    )
                )
                while not task.done():
                    if must_stop(cancel_event, deadline):
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        return None
                    await asyncio.sleep(0.05)
                return await task

            result = asyncio.run(collect())
            if result is None:
                from datetime import datetime, timezone

                reason = (
                    "cancelled"
                    if cancel_event is not None and cancel_event.is_set()
                    else "host_deadline"
                )
                results.append(
                    OpcUaInventory(
                        "opcua_tcp",
                        port.port,
                        "suspected",
                        ("tcp_candidate",),
                        "partial" if reason == "cancelled" else "timed_out",
                        datetime.now(timezone.utc),
                        reason_code=reason,
                        reason_codes=(reason,),
                        request_count_known=False,
                    )
                )
                pending_reason = (
                    "cancelled"
                    if cancel_event is not None and cancel_event.is_set()
                    else "host_deadline"
                )
                results.extend(
                    _opcua_unstarted(item, pending_reason)
                    for item in candidates[candidates.index(port) + 1 :]
                )
                break
        except (OSError, RuntimeError, ValueError):
            from datetime import datetime, timezone
            results.append(
                OpcUaInventory(
                    "opcua_tcp", port.port, "suspected", ("tcp_candidate",),
                    "failed", datetime.now(timezone.utc),
                    reason_code="service_error", reason_codes=("service_error",),
                )
            )
            continue
        results.append(result)
        request_budget = (
            max(0, request_budget - result.requests_sent)
            if result.request_count_known
            else 0
        )
        if request_budget <= 0:
            results.extend(
                _opcua_unstarted(item, "request_budget_exhausted")
                for item in candidates[candidates.index(port) + 1 :]
            )
            break
    results.extend(_opcua_unstarted(item, "service_limit") for item in limited)
    unique: dict[int, OpcUaInventory] = {}
    for item in results:
        unique.setdefault(item.port, item)
    return list(unique.values())


def _opcua_unstarted(port, reason: str) -> OpcUaInventory:
    from datetime import datetime, timezone
    outcome = "timed_out" if reason == "host_deadline" else "partial"
    return OpcUaInventory(
        "opcua_tcp", port.port, "suspected", ("tcp_candidate",), outcome,
        datetime.now(timezone.utc), reason_code=reason, reason_codes=(reason,),
    )


def _map_opcua_service(
    service: OpcUaInventory,
    host: str,
    *,
    cancel_event: threading.Event | None,
    deadline: float | None,
    request_budget: int,
    pacing_ms: int = 100,
):
    if service.confidence != "confirmed" or not service.client_endpoints:
        from agent.ot.opcua.models import OpcUaMappingResult

        return OpcUaMappingResult("skipped", ("invalid_response",))
    if must_stop(cancel_event, deadline):
        return _opcua_skipped_mapping(
            "cancelled" if cancel_event and cancel_event.is_set() else "host_deadline"
        )
    remaining = max(0.1, min(90.0, deadline - perf_counter() if deadline else 90.0))

    async def run():
        task = asyncio.create_task(
            map_opcua_service(
                OpcUaClient(),
                host,
                service.port,
                service.client_endpoints,
                request_budget=min(32, request_budget),
                timeout=min(2.0, remaining),
                deadline=remaining,
                pacing_ms=pacing_ms,
            )
        )
        while not task.done():
            if must_stop(cancel_event, deadline):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return _opcua_skipped_mapping(
                    "cancelled"
                    if cancel_event and cancel_event.is_set()
                    else "host_deadline",
                    request_count_known=False,
                )
            await asyncio.sleep(0.05)
        return await task

    try:
        return asyncio.run(run())
    except Exception:
        from agent.ot.opcua.models import OpcUaMappingResult

        return OpcUaMappingResult("failed", ("service_error",))


def _opcua_skipped_mapping(reason: str, *, request_count_known: bool = True):
    from agent.ot.opcua.models import OpcUaMappingResult

    return OpcUaMappingResult(
        "skipped", (reason,), request_count_known=request_count_known
    )


def _mapping_request_count(mapping) -> int:
    return min(32, max(0, mapping.requests_sent))


def build_host_payload(
    host: HostInfo,
    *,
    agent_ip: str | None = None,
    machine_type: MachineType | None = None,
    device_profile: DeviceProfilePayload | None = None,
) -> HostPayload:
    return HostPayload(
        ip=host.ip,
        mac=host.identity.mac,
        hostname="DMITRI" if agent_ip == host.ip else (host.hostname or host.ip),
        vendor=host.identity.vendor,
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
        ]
        + [_build_opcua_payload(service) for service in host.opcua_services],
        machine_type=machine_type,
        device_profile=device_profile,
    )


def _build_opcua_payload(service: OpcUaInventory) -> OpcUaTcpServicePayload:
    inventory_phase = {
        "status": service.inventory_status,
        "reason_codes": list(
            service.reason_codes
            or ((service.reason_code,) if service.reason_code else ())
        ),
        "truncated": service.truncated,
        "observed_at": service.observed_at,
    }
    mapping = None
    if service.mapping is not None:
        result = service.mapping
        mapping = {
            "phase": {
                "status": result.status,
                "reason_codes": list(result.reason_codes),
                "truncated": result.truncated,
                "observed_at": result.observed_at,
            },
            "nodes": [
                node.__dict__
                if hasattr(node, "__dict__")
                else {name: getattr(node, name) for name in node.__slots__}
                for node in result.nodes
            ],
            "references": [
                item.__dict__
                if hasattr(item, "__dict__")
                else {name: getattr(item, name) for name in item.__slots__}
                for item in result.references
            ],
            "references_observed": result.references_observed,
            "value_reads_attempted": result.value_reads_attempted,
            "selected_endpoint_index": result.selected_endpoint_index,
            "anonymous_session_activated": result.anonymous_session_activated,
            "browse_succeeded": result.browse_succeeded,
            "application_value_read_succeeded": result.application_value_read_succeeded,
            "value_good_count": result.value_good_count,
            "security_mode": {
                "value": next(iter(result.security_mode.values()), "None"),
                "source": "get_endpoints",
                "status": "Good",
            },
            "security_policy": {
                "value": next(iter(result.security_policy.values()), "None"),
                "source": "get_endpoints",
                "status": "Good",
            },
        }
    return OpcUaTcpServicePayload.model_validate(
        {
            "protocol": "opcua_tcp",
            "port": service.port,
            "confidence": service.confidence,
            "evidence_sources": list(service.evidence_sources),
                "write_requests_sent": service.write_requests_sent
                + (
                    service.mapping.write_requests_sent
                    if service.mapping
                    else 0
                ),
            "observation": {
                "schema_version": 1,
                "inventory_phase": inventory_phase,
                "identity": service.identity or None,
                "certificate_sha256": service.certificate_sha256,
                "endpoints": [
                    {
                        "endpoint_url": item.endpoint_url,
                        "security_policy_uri": item.security_policy_uri,
                        "security_mode": item.security_mode,
                        "transport_profile_uri": item.transport_profile_uri,
                        "security_level": item.security_level,
                        "user_token_count": item.user_token_count,
                        "user_token_types": list(item.user_token_types),
                        "target_matches": item.target_matches,
                    }
                    for item in service.endpoints
                ],
                "mapping": mapping,
            },
        }
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
        "agent_version": installed_version(),
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
                "nspi_policy_version": 2,
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
        opcua_services = [
            service for host in hosts or [] for service in host.opcua_services
        ]
        metadata.update(
            {
                "opcua_candidates": len(opcua_services),
                "opcua_confirmed": sum(
                    service.confidence == "confirmed" for service in opcua_services
                ),
                "opcua_requests_sent": sum(
                    service.requests_sent for service in opcua_services
                )
                + sum(
                    service.mapping.requests_sent
                    for service in opcua_services
                    if service.mapping
                ),
                "opcua_request_counts_incomplete": any(
                    not service.request_count_known
                    or (
                        service.mapping is not None
                        and not service.mapping.request_count_known
                    )
                    for service in opcua_services
                ),
                "opcua_anonymous_value_reads": sum(
                    service.mapping.value_reads_attempted
                    for service in opcua_services
                    if service.mapping
                ),
                "opcua_limited_services": sum(
                    service.inventory_status != "completed"
                    or (
                        service.mapping is not None
                        and service.mapping.status not in {"completed", "skipped"}
                    )
                    for service in opcua_services
                ),
                "industrial_requests_sent": sum(
                    service.requests_sent for service in modbus_services
                )
                + sum(service.requests_sent for service in opcua_services)
                + sum(
                    service.mapping.requests_sent
                    for service in opcua_services
                    if service.mapping
                ),
                "industrial_request_counts_incomplete": any(
                    not service.request_count_known
                    or (
                        service.mapping is not None
                        and not service.mapping.request_count_known
                    )
                    for service in opcua_services
                ),
            }
        )
        if ot_result.stage_deadline_reached:
            metadata["industrial_stage_deadline_reached"] = True
            if ot_result.stage_deadline_seconds is not None:
                metadata["industrial_stage_deadline_seconds"] = (
                    ot_result.stage_deadline_seconds
                )
    if targeted_summary is not None:
        metadata.update(
            {
                "targeted_units_eligible": targeted_summary.eligible,
                "targeted_units_planned": targeted_summary.planned,
                "targeted_units_omitted": targeted_summary.omitted,
                "targeted_units_omitted_unlisted": targeted_summary.omitted_unlisted,
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
