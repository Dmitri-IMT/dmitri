from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from agent.ot.modbus.client import ModbusClientController, probe_device_identification
from agent.ot.modbus.merge import merge_unit
from agent.ot.modbus.models import ModbusService, ModbusUnit
from agent.ot.modbus.nse import parse_modbus_discover
from agent.ot.policy import OtAutomationPolicy, must_stop, pace_or_stop
from agent.scanner.models import HostInfo, PortInfo

LOGGER = logging.getLogger(__name__)

DEFAULT_FALLBACK_UNIT_ID = 1
MAX_IDENTIFICATION_FALLBACKS_PER_HOST = 4

IdentificationProbe = Callable[..., ModbusUnit]


def inventory_modbus_host(
    host: HostInfo,
    *,
    policy: OtAutomationPolicy | None = None,
    timeout: float = 1.5,
    cancel_event: threading.Event | None = None,
    probe: IdentificationProbe = probe_device_identification,
    controller: ModbusClientController | None = None,
    sleep: Callable[[float], None] = time.sleep,
    deadline: float | None = None,
    request_budget: int = 32,
) -> list[ModbusService]:
    """Build a bounded Modbus inventory for one host."""

    effective_policy = policy or OtAutomationPolicy()
    services: list[ModbusService] = []
    remaining_requests = max(0, request_budget)
    for port in sorted(host.open_ports, key=lambda item: item.port):
        if not _is_modbus_candidate(port):
            continue
        if must_stop(cancel_event, deadline):
            break
        services.append(
            _inventory_port(
                host.ip,
                port,
                policy=effective_policy,
                timeout=timeout,
                cancel_event=cancel_event,
                probe=probe,
                controller=controller,
                sleep=sleep,
                deadline=deadline,
                request_budget=remaining_requests,
            )
        )
        remaining_requests = max(0, remaining_requests - services[-1].requests_sent)
    return services


def has_modbus_candidate(host: HostInfo) -> bool:
    return any(_is_modbus_candidate(port) for port in host.open_ports)


def _inventory_port(
    host: str,
    port: PortInfo,
    *,
    policy: OtAutomationPolicy,
    timeout: float,
    cancel_event: threading.Event | None,
    probe: IdentificationProbe,
    controller: ModbusClientController | None,
    sleep: Callable[[float], None],
    deadline: float | None,
    request_budget: int,
) -> ModbusService:
    evidence = ["tcp-port"]
    service_name = port.service.name.lower()
    service_confirms_modbus = "modbus" in service_name or service_name == "mbap"
    if service_confirms_modbus:
        evidence.append("nmap-service")

    units: dict[int, ModbusUnit] = {}
    parse_failures = 0
    requests_sent = 0
    timeouts = 0
    try:
        scripts = [
            script for script in port.scripts if script.script_id == "modbus-discover"
        ]
        if scripts:
            evidence.append("modbus-discover")
        for script in scripts:
            discover = parse_modbus_discover(script)
            parse_failures += discover.parse_failures
            for unit in discover.units:
                merge_unit(units, unit)

        fallback_ids = [
            unit_id
            for unit_id, unit in sorted(units.items())
            if unit_id != 0
            and (
                unit.device_identification is None
                or not unit.device_identification.has_structured_fields
            )
        ][:MAX_IDENTIFICATION_FALLBACKS_PER_HOST]
        fallback_ids = fallback_ids[: max(0, request_budget)]
        if not units and request_budget > 0:
            fallback_ids = [DEFAULT_FALLBACK_UNIT_ID]

        delay_seconds = policy.inter_request_delay_ms / 1000
        for unit_id in fallback_ids:
            reason = pace_or_stop(sleep, delay_seconds, cancel_event, deadline)
            if reason == "cancel":
                break
            if reason == "deadline":
                merge_unit(
                    units,
                    ModbusUnit(unit_id=unit_id, status="skipped"),
                )
                continue
            probe_options = {"timeout": timeout}
            if controller is not None:
                probe_options["controller"] = controller
            try:
                result = probe(host, port.port, unit_id, **probe_options)
            except Exception as exc:
                LOGGER.exception(
                    "Modbus identification probe failed for %s:%s unit %s",
                    host,
                    port.port,
                    unit_id,
                )
                result = ModbusUnit(
                    unit_id=unit_id,
                    status="error",
                    error=type(exc).__name__,
                )
            requests_sent += int(result.request_sent)
            timeouts += int(result.status == "timeout")
            merge_unit(units, result)
        if requests_sent:
            evidence.append("pymodbus")
    except Exception:
        LOGGER.exception(
            "Modbus inventory failed for %s:%s after partial collection",
            host,
            port.port,
        )
        evidence.append("inventory-error")

    confidence = (
        "confirmed"
        if service_confirms_modbus
        or any(unit.status in {"responding", "exception"} for unit in units.values())
        else "suspected"
    )
    return ModbusService(
        port=port.port,
        confidence=confidence,
        evidence_sources=evidence,
        units=sorted(units.values(), key=lambda unit: unit.unit_id),
        requests_sent=requests_sent,
        timeouts=timeouts,
        parse_failures=parse_failures,
    )


def _is_modbus_candidate(port: PortInfo) -> bool:
    if port.protocol.lower() != "tcp":
        return False
    service_name = port.service.name.lower()
    return port.port == 502 or "modbus" in service_name or service_name == "mbap"
