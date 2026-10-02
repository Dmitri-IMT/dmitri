"""Host profiling from accepted scanner evidence."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from agent.normalize.contracts import AssessmentEvidencePayload, DeviceProfilePayload
from agent.scanner.models import HostInfo

from .evidence import (
    _bounded_evidence,
    _bounded_messages,
    _evidence,
    _has_token,
    _matching_type_tokens,
    _port_evidence_key,
    _roles_for_text,
    _safe_text,
    _script_facts,
)
from .policy import (
    AMBIGUOUS_VENDOR_NAMES,
    MACHINE_SIGNAL_RULES,
    MAX_CONFLICTS,
    MAX_EVIDENCE_VALUE_CHARS,
    MAX_LIMITATIONS,
    OS_DEVICE_TYPE_RULES,
    SIGNAL_WEIGHTS,
    AssessmentConfidence,
    EvidenceKind,
    ExposureRole,
    MachineType,
)


@dataclass(frozen=True, slots=True)
class _Signal:
    machine_type: MachineType
    kind: str
    source: str
    weight: int
    evidence: AssessmentEvidencePayload


@dataclass(frozen=True, slots=True)
class _ProductFact:
    source: str
    value: str
    kind: EvidenceKind
    machine_types: frozenset[MachineType]


def _is_locally_administered(mac: str | None) -> bool:
    if not mac:
        return False
    try:
        return bool(int(mac.split(":", 1)[0], 16) & 0x02)
    except (ValueError, IndexError):
        return False


def _add_signal(
    signals: dict[tuple[MachineType, str, str], _Signal],
    machine_type: MachineType,
    kind: str,
    source: str,
    weight: int,
    evidence: AssessmentEvidencePayload | None,
) -> None:
    if evidence is None:
        return
    key = (machine_type, kind, source)
    signals.setdefault(
        key,
        _Signal(machine_type, kind, source, weight, evidence),
    )


def _service_signals(host: HostInfo) -> list[_Signal]:
    signals: dict[tuple[MachineType, str, str], _Signal] = {}
    open_ports = sorted(
        (port for port in host.ports if port.state == "open"),
        key=lambda port: (port.port, _port_evidence_key(port)),
    )
    ports = {port.port for port in open_ports}
    names = {port.service.name.casefold().strip() for port in open_ports}

    router_service_set = (
        (53 in ports or "domain" in names) and bool({80, 443, 8080} & ports)
    ) or ((1900 in ports or "upnp" in names) and (53 in ports or "domain" in names))

    for port in open_ports:
        endpoint = f"{port.port}/{port.protocol}"
        name = _safe_text(port.service.name, MAX_EVIDENCE_VALUE_CHARS) or "unknown"
        lowered_name = name.casefold()
        for machine_type, rules in MACHINE_SIGNAL_RULES.items():
            if machine_type in {"router", "unknown"}:
                continue
            service_rules = rules["service"]
            if port.port in service_rules:
                _add_signal(
                    signals,
                    machine_type,
                    "port",
                    endpoint,
                    SIGNAL_WEIGHTS["port"],
                    _evidence("port", "nmap", f"{endpoint} open"),
                )
            if any(
                isinstance(token, str) and _has_token(lowered_name, token)
                for token in service_rules
            ):
                _add_signal(
                    signals,
                    machine_type,
                    "service",
                    endpoint,
                    SIGNAL_WEIGHTS["service"],
                    _evidence("service", endpoint, name),
                )

        for cpe in port.service.cpes:
            safe_cpe = _safe_text(cpe, MAX_EVIDENCE_VALUE_CHARS)
            if safe_cpe is None:
                continue
            for machine_type in _matching_type_tokens(safe_cpe):
                _add_signal(
                    signals,
                    machine_type,
                    "cpe",
                    endpoint,
                    SIGNAL_WEIGHTS["cpe"],
                    _evidence("cpe", endpoint, safe_cpe),
                )
        for product in (port.service.product, port.service.version):
            safe_product = _safe_text(product, MAX_EVIDENCE_VALUE_CHARS)
            if safe_product is None:
                continue
            for machine_type in _matching_type_tokens(safe_product):
                _add_signal(
                    signals,
                    machine_type,
                    "product",
                    endpoint,
                    SIGNAL_WEIGHTS["product"],
                    _evidence("version", endpoint, safe_product),
                )

    if router_service_set:
        router_evidence = _evidence(
            "service", "open-endpoint-set", "DNS with web or UPnP service"
        )
        _add_signal(
            signals,
            "router",
            "service",
            "open-endpoint-set",
            SIGNAL_WEIGHTS["service"],
            router_evidence,
        )
        _add_signal(
            signals,
            "router",
            "port",
            "open-endpoint-set",
            SIGNAL_WEIGHTS["port"],
            _evidence("port", "nmap", "router service port combination"),
        )
    return list(signals.values())


def _profile_host(host: HostInfo) -> tuple[MachineType, DeviceProfilePayload]:
    signals = _service_signals(host)
    locally_administered = _is_locally_administered(host.identity.mac)
    vendor = _safe_text(host.identity.vendor, MAX_EVIDENCE_VALUE_CHARS)
    vendor_known = vendor is not None and vendor.casefold() != "unknown"
    manufacturer = None if locally_administered else vendor if vendor_known else None
    conflicts: list[str] = []
    limitations: list[str] = []
    product_values: list[_ProductFact] = []
    model_values: list[tuple[str, str]] = []
    supplemental_evidence: list[AssessmentEvidencePayload] = []

    for observation in host.targeted_results:
        for item in observation.observations:
            if item.kind == "service_identity":
                evidence = _evidence(
                    "service", f"targeted:{item.observation_key}", item.summary
                )
                if evidence:
                    supplemental_evidence.append(evidence)
            elif item.kind == "device_identity":
                evidence = _evidence(
                    "industrial", f"targeted:{item.observation_key}", item.summary
                )
                if evidence:
                    supplemental_evidence.append(evidence)
                    product_values.append(
                        _ProductFact(
                            f"targeted:{item.observation_key}",
                            item.summary,
                            "industrial",
                            frozenset(),
                        )
                    )

    if locally_administered:
        limitations.append(
            "Locally administered MAC address; OUI manufacturer unavailable."
        )
    elif vendor_known:
        lowered_vendor = vendor.casefold()
        if not any(name in lowered_vendor for name in AMBIGUOUS_VENDOR_NAMES):
            for machine_type, rules in MACHINE_SIGNAL_RULES.items():
                if machine_type == "unknown" or not any(
                    name in lowered_vendor for name in rules["vendor"]
                ):
                    continue
                item = _evidence("manufacturer", "observed MAC vendor", vendor)
                if item is not None:
                    signals.append(
                        _Signal(
                            machine_type,
                            "manufacturer",
                            "observed MAC vendor",
                            SIGNAL_WEIGHTS["manufacturer"],
                            item,
                        )
                    )

    hostname = _safe_text(host.hostname, MAX_EVIDENCE_VALUE_CHARS)
    generic_hostnames = {host.ip.casefold(), "unknown", "localhost"}
    if hostname and hostname.casefold() not in generic_hostnames:
        hostname_evidence = _evidence("hostname", "discovery", hostname)
        if hostname_evidence:
            supplemental_evidence.append(hostname_evidence)
        if hostname_evidence:
            for machine_type in _matching_type_tokens(hostname):
                signals.append(
                    _Signal(
                        machine_type,
                        "hostname",
                        "discovery",
                        SIGNAL_WEIGHTS["hostname"],
                        hostname_evidence,
                    )
                )

    for port in sorted(
        host.open_ports,
        key=lambda item: (item.port, item.protocol, _port_evidence_key(item)),
    ):
        endpoint = f"{port.port}/{port.protocol}"
        product = _safe_text(port.service.product, MAX_EVIDENCE_VALUE_CHARS)
        if product:
            candidates = _matching_type_tokens(product)
            if candidates and len(product.split()) > 1:
                product_values.append(
                    _ProductFact(endpoint, product, "version", frozenset(candidates))
                )
            for candidate in candidates:
                item = _evidence("version", endpoint, product)
                if item:
                    signals.append(
                        _Signal(
                            candidate,
                            "product",
                            endpoint,
                            SIGNAL_WEIGHTS["product"],
                            item,
                        )
                    )
        for cpe in port.service.cpes:
            safe_cpe = _safe_text(cpe, MAX_EVIDENCE_VALUE_CHARS)
            if safe_cpe is None:
                continue
            candidates = _matching_type_tokens(safe_cpe)
            if candidates:
                product_values.append(
                    _ProductFact(
                        endpoint,
                        safe_cpe,
                        "cpe",
                        frozenset(candidates),
                    )
                )
        protocol_roles: set[ExposureRole] = set()
        observed_roles = _roles_for_text(port.service.name, structured=False)
        for kind, value in _script_facts(port.scripts):
            script_evidence = _evidence(kind, endpoint, value)
            if script_evidence:
                supplemental_evidence.append(script_evidence)
            candidates = _matching_type_tokens(value)
            signal_kind = "protocol" if kind == "protocol" else "product"
            weight = SIGNAL_WEIGHTS[signal_kind]
            for candidate in candidates:
                item = _evidence(kind, endpoint, value)
                if item:
                    signals.append(
                        _Signal(candidate, signal_kind, endpoint, weight, item)
                    )
            product_bearing_fact = kind == "banner" or (
                kind == "certificate" and value.casefold().startswith("subject: ")
            )
            if product_bearing_fact and candidates:
                product_values.append(
                    _ProductFact(
                        endpoint,
                        value,
                        kind,
                        frozenset(candidates),
                    )
                )
            if kind == "protocol":
                protocol_roles.update(_roles_for_text(value, structured=True))
        observed_name = port.service.name.casefold().strip()
        observed_is_label = bool(observed_name and observed_name != "unknown")
        if observed_is_label and protocol_roles and observed_roles != protocol_roles:
            conflicts.append(
                f"Observed service label on {endpoint} conflicts with "
                "protocol evidence."
            )

    os_info = host.operating_system
    if os_info is not None and os_info.accuracy >= 90 and os_info.device_type:
        device_type = os_info.device_type.casefold().strip()
        machine_type = OS_DEVICE_TYPE_RULES.get(device_type)
        evidence = _evidence(
            "operating_system",
            "nmap os fingerprint",
            f"{os_info.name} ({os_info.accuracy}%); {os_info.device_type}",
        )
        if evidence:
            supplemental_evidence.append(evidence)
        if machine_type and evidence:
            signals.append(
                _Signal(
                    machine_type,
                    "operating_system",
                    "nmap os fingerprint",
                    SIGNAL_WEIGHTS["operating_system"],
                    evidence,
                )
            )
        for cpe in os_info.cpes:
            safe_cpe = _safe_text(cpe, MAX_EVIDENCE_VALUE_CHARS)
            if safe_cpe is None:
                continue
            candidates = _matching_type_tokens(safe_cpe)
            if candidates:
                product_values.append(
                    _ProductFact(
                        "nmap os fingerprint",
                        safe_cpe,
                        "cpe",
                        frozenset(candidates),
                    )
                )
            for candidate in candidates:
                item = _evidence("cpe", "nmap os fingerprint", safe_cpe)
                if item:
                    signals.append(
                        _Signal(
                            candidate,
                            "cpe",
                            "nmap os fingerprint",
                            SIGNAL_WEIGHTS["cpe"],
                            item,
                        )
                    )

    industrial_vendors: dict[str, int] = defaultdict(int)
    for service in sorted(host.industrial_services, key=lambda item: item.port):
        for unit in sorted(service.units, key=lambda item: item.unit_id):
            identity = unit.device_identification
            if identity is None:
                continue
            source = f"modbus {service.port}/tcp unit {unit.unit_id}"
            safe_vendor = _safe_text(identity.vendor_name, MAX_EVIDENCE_VALUE_CHARS)
            if safe_vendor:
                industrial_vendors[safe_vendor] += SIGNAL_WEIGHTS["industrial"]
            for value in (identity.product_name, identity.product_code):
                safe = _safe_text(value, MAX_EVIDENCE_VALUE_CHARS)
                if safe:
                    product_values.append(
                        _ProductFact(source, safe, "industrial", frozenset())
                    )
            for value in (identity.model_name, identity.product_code):
                safe = _safe_text(value, MAX_EVIDENCE_VALUE_CHARS)
                if safe:
                    model_values.append((source, safe))

    if industrial_vendors:
        best_score = max(industrial_vendors.values())
        best = sorted(
            name for name, score in industrial_vendors.items() if score == best_score
        )
        if len(best) == 1:
            industrial_manufacturer = best[0]
            manufacturer_disagrees = manufacturer and (
                manufacturer.casefold() != industrial_manufacturer.casefold()
            )
            if manufacturer_disagrees:
                conflicts.append(
                    "Manufacturer evidence disagrees: "
                    f"{manufacturer} and {industrial_manufacturer}."
                )
            manufacturer = industrial_manufacturer
        else:
            manufacturer = None
            conflicts.append("Manufacturer evidence is tied: " + ", ".join(best) + ".")

    scores: dict[MachineType, int] = defaultdict(int)
    kinds: dict[MachineType, set[str]] = defaultdict(set)
    unique_signals: dict[tuple[MachineType, str, str], _Signal] = {}
    for signal in signals:
        unique_signals.setdefault(
            (signal.machine_type, signal.kind, signal.source), signal
        )
    for signal in unique_signals.values():
        scores[signal.machine_type] += signal.weight
        kinds[signal.machine_type].add(signal.kind)

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    leader: MachineType = ranked[0][0] if ranked else "unknown"
    leader_score = ranked[0][1] if ranked else 0
    runner_up = ranked[1] if len(ranked) > 1 else None
    conflicting_type = bool(
        runner_up and runner_up[1] >= 3 and leader_score - runner_up[1] <= 1
    )
    if leader_score < 2:
        machine_type: MachineType = "unknown"
        confidence: AssessmentConfidence = "unknown"
    elif conflicting_type:
        machine_type = "unknown"
        confidence = "low"
        conflicts.append(
            f"Machine-type evidence is close between {leader} ({leader_score}) and "
            f"{runner_up[0]} ({runner_up[1]})."
        )
    else:
        machine_type = leader
        if leader_score <= 3:
            confidence = "low"
        elif leader_score <= 5:
            confidence = "medium"
        else:
            confidence = "high" if len(kinds[leader]) >= 2 else "low"

    relevant_types = (
        {leader, runner_up[0]} if conflicting_type and runner_up else {machine_type}
    )
    profile_evidence = [
        signal.evidence
        for signal in unique_signals.values()
        if signal.machine_type in relevant_types and signal.machine_type != "unknown"
    ]
    profile_evidence.extend(supplemental_evidence)
    if manufacturer:
        item = _evidence("manufacturer", "assessment", manufacturer)
        if item:
            profile_evidence.append(item)
    if not profile_evidence:
        ordered_ports = sorted(
            host.open_ports, key=lambda item: (item.port, item.protocol)
        )
        for port in ordered_ports:
            endpoint = f"{port.port}/{port.protocol}"
            for item in (
                _evidence("port", "nmap", f"{endpoint} open"),
                _evidence("service", endpoint, port.service.name or "unknown"),
            ):
                if item:
                    profile_evidence.append(item)

    product_family = None
    if product_values:
        corroborated = machine_type != "unknown" and len(kinds[machine_type]) >= 2
        eligible_products = [
            fact
            for fact in product_values
            if fact.kind == "industrial"
            or (corroborated and machine_type in fact.machine_types)
        ]
        if eligible_products:
            ordered_products = sorted(
                eligible_products,
                key=lambda item: (item.value.casefold(), item.source, item.kind),
            )
            selected_product = ordered_products[0]
            product_family = selected_product.value
            item = _evidence(
                selected_product.kind,
                selected_product.source,
                product_family,
            )
            if item:
                profile_evidence.append(item)
    if product_family is None:
        limitations.append("Available evidence does not support a product family.")

    model = None
    if model_values:
        model_source, model = sorted(model_values, key=lambda item: (item[1], item[0]))[
            0
        ]
        item = _evidence("industrial", model_source, model)
        if item:
            profile_evidence.append(item)
    if model is None:
        limitations.append("Available evidence does not support an exact model.")
    if machine_type == "unknown":
        limitations.append("Available evidence does not support a machine type.")

    return machine_type, DeviceProfilePayload(
        manufacturer=manufacturer,
        product_family=product_family,
        model=model,
        confidence=confidence,
        evidence=_bounded_evidence(profile_evidence),
        conflicts=_bounded_messages(conflicts, MAX_CONFLICTS),
        limitations=_bounded_messages(limitations, MAX_LIMITATIONS),
    )
