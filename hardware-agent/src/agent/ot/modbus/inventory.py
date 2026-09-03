from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from agent.ot.modbus.client import ModbusClientController, probe_device_identification
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.ot.modbus.nse import parse_modbus_discover
from agent.scanner.models import HostInfo, PortInfo

LOGGER = logging.getLogger(__name__)

DEFAULT_FALLBACK_UNIT_ID = 1
MAX_IDENTIFICATION_FALLBACKS_PER_HOST = 4

IdentificationProbe = Callable[..., ModbusUnit]


def inventory_modbus_host(
    host: HostInfo,
    *,
    timeout: float = 1.5,
    cancel_event: threading.Event | None = None,
    probe: IdentificationProbe = probe_device_identification,
    controller: ModbusClientController | None = None,
) -> list[ModbusService]:
    """Build a bounded Modbus inventory for one host."""

    services: list[ModbusService] = []
    for port in sorted(host.open_ports, key=lambda item: item.port):
        if not _is_modbus_candidate(port):
            continue
        if cancel_event is not None and cancel_event.is_set():
            break
        try:
            services.append(
                _inventory_port(
                    host.ip,
                    port,
                    timeout=timeout,
                    cancel_event=cancel_event,
                    probe=probe,
                    controller=controller,
                )
            )
        except Exception:
            LOGGER.exception("Modbus inventory failed for %s:%s", host.ip, port.port)
            services.append(
                ModbusService(
                    port=port.port,
                    confidence="suspected",
                    evidence_sources=["tcp-port"],
                )
            )
    return services


def has_modbus_candidate(host: HostInfo) -> bool:
    return any(_is_modbus_candidate(port) for port in host.open_ports)


def _inventory_port(
    host: str,
    port: PortInfo,
    *,
    timeout: float,
    cancel_event: threading.Event | None,
    probe: IdentificationProbe,
    controller: ModbusClientController | None,
) -> ModbusService:
    evidence = ["tcp-port"]
    service_name = port.service.name.lower()
    service_confirms_modbus = "modbus" in service_name or service_name == "mbap"
    if service_confirms_modbus:
        evidence.append("nmap-service")

    units: dict[int, ModbusUnit] = {}
    scripts = [
        script for script in port.scripts if script.script_id == "modbus-discover"
    ]
    if scripts:
        evidence.append("modbus-discover")
    for script in scripts:
        for unit in parse_modbus_discover(script):
            _merge_unit(units, unit)

    fallback_ids = [
        unit_id
        for unit_id, unit in sorted(units.items())
        if unit_id != 0
        and (
            unit.device_identification is None
            or not unit.device_identification.has_structured_fields
        )
    ][:MAX_IDENTIFICATION_FALLBACKS_PER_HOST]
    if not units:
        fallback_ids = [DEFAULT_FALLBACK_UNIT_ID]

    requests_sent = 0
    timeouts = 0
    for unit_id in fallback_ids:
        if cancel_event is not None and cancel_event.is_set():
            break
        probe_options = {"timeout": timeout}
        if controller is not None:
            probe_options["controller"] = controller
        result = probe(host, port.port, unit_id, **probe_options)
        requests_sent += 1
        timeouts += int(result.status == "timeout")
        _merge_unit(units, result)
    if requests_sent:
        evidence.append("pymodbus")

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
    )


def _is_modbus_candidate(port: PortInfo) -> bool:
    if port.protocol.lower() != "tcp":
        return False
    service_name = port.service.name.lower()
    return port.port == 502 or "modbus" in service_name or service_name == "mbap"


def _merge_unit(units: dict[int, ModbusUnit], candidate: ModbusUnit) -> None:
    current = units.get(candidate.unit_id)
    if current is None:
        units[candidate.unit_id] = candidate
        return

    if candidate.status in {"responding", "exception"}:
        current.status = candidate.status
        current.exception_code = candidate.exception_code
        current.error = candidate.error
    elif current.status not in {"responding", "exception"}:
        current.status = candidate.status
        current.error = candidate.error

    if candidate.device_identification is not None:
        if current.device_identification is None:
            current.device_identification = candidate.device_identification
        else:
            _merge_identification(
                current.device_identification,
                candidate.device_identification,
            )


def _merge_identification(
    current: ModbusDeviceIdentification,
    candidate: ModbusDeviceIdentification,
) -> None:
    for field_name in (
        "vendor_name",
        "product_code",
        "major_minor_revision",
        "vendor_url",
        "product_name",
        "model_name",
        "user_application_name",
    ):
        if getattr(current, field_name) is None:
            setattr(current, field_name, getattr(candidate, field_name))
    current.objects.update(candidate.objects)
