from __future__ import annotations

import re
from dataclasses import dataclass

from agent.ot.modbus.models import ModbusDeviceIdentification, ModbusService
from agent.scanner.models import HostInfo

FINGERPRINT_EVIDENCE_SOURCE = "fc43-fingerprint-catalog"

_VERSION_PATTERN = re.compile(r"^v?([0-9]+(?:[.][0-9]+){1,3})$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FingerprintCandidate:
    family: str
    cpe: str
    confidence: str = "high"


def correlate_fc43_fingerprints(host: HostInfo) -> list[FingerprintCandidate]:
    """Attach reviewed high-confidence FC43 CPEs to their observed TCP port."""

    port_index = {port.port: port for port in host.ports}
    candidates: list[FingerprintCandidate] = []
    for service in host.industrial_services:
        service_candidates = _service_candidates(service)
        if not service_candidates:
            continue
        port = port_index.get(service.port)
        if port is None:
            continue
        for candidate in service_candidates:
            if candidate.cpe not in port.service.cpes:
                port.service.cpes.append(candidate.cpe)
            if candidate not in candidates:
                candidates.append(candidate)
        if FINGERPRINT_EVIDENCE_SOURCE not in service.evidence_sources:
            service.evidence_sources.append(FINGERPRINT_EVIDENCE_SOURCE)
    return candidates


def fingerprint_identification(
    identification: ModbusDeviceIdentification,
) -> FingerprintCandidate | None:
    vendor = _canonical(identification.vendor_name or "")
    if vendor not in {"schneiderelectric", "schneiderautomation"}:
        return None
    version = _normalise_version(identification.major_minor_revision)
    if version is None:
        return None
    product_values = {
        _canonical(value)
        for value in (
            identification.product_code,
            identification.product_name,
            identification.model_name,
        )
        if value
    }
    family = _schneider_family(product_values)
    if family is None:
        return None
    cpe = (
        "cpe:2.3:o:schneider-electric:"
        f"modicon_{family}_firmware:{version}:*:*:*:*:*:*:*"
    )
    return FingerprintCandidate(family=f"Modicon {family.upper()}", cpe=cpe)


def _service_candidates(service: ModbusService) -> list[FingerprintCandidate]:
    found: list[FingerprintCandidate] = []
    for unit in service.units:
        if (
            unit.device_identification is None
            or "pymodbus-fc43" not in unit.identification_sources
        ):
            continue
        candidate = fingerprint_identification(unit.device_identification)
        if candidate is not None and candidate not in found:
            found.append(candidate)
    return found


def _normalise_version(value: str | None) -> str | None:
    if value is None:
        return None
    match = _VERSION_PATTERN.fullmatch(value.strip())
    return match.group(1) if match else None


def _schneider_family(products: set[str]) -> str | None:
    if any(
        value in {"m340", "modiconm340", "bmxp34"} or value.startswith("bmxp34")
        for value in products
    ):
        return "m340"
    if any(
        value in {"m580", "modiconm580"} or value.startswith(("bmep58", "bmeh58"))
        for value in products
    ):
        return "m580"
    return None


def _canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())
