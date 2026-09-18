"""Pure local assessment of accepted scanner evidence."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Iterable

from agent.normalize.contracts import (
    AssessmentEvidencePayload,
    DeviceProfilePayload,
    ExposurePayload,
)
from agent.ot.modbus.models import ModbusService
from agent.scanner.models import HostInfo, PortInfo, ScriptResult

from .policy import (
    AMBIGUOUS_VENDOR_NAMES,
    EXPOSURE_ROLE_PORTS,
    EXPOSURE_ROLE_TOKENS,
    MACHINE_SIGNAL_RULES,
    MAX_CONFLICTS,
    MAX_EVIDENCE_ITEMS,
    MAX_EVIDENCE_SOURCE_CHARS,
    MAX_EVIDENCE_VALUE_CHARS,
    MAX_LIMITATIONS,
    MAX_REASON_CHARS,
    OS_DEVICE_TYPE_RULES,
    PRIORITY_CLEARTEXT_TOKENS,
    PRODUCT_TYPE_TOKENS,
    REVIEW_ROLES,
    SIGNAL_WEIGHTS,
    AssessmentConfidence,
    EvidenceKind,
    ExposureAttention,
    ExposureConfidence,
    ExposureRole,
    MachineType,
)

_PRIVATE_KEY_PATTERN = re.compile(r"-----begin [^-]*private key-----", re.IGNORECASE)
_CREDENTIAL_PATTERN = re.compile(
    r"(?:(?:password|passwd|token|secret|api[ _-]?key|authorization|cookie)"
    r"\s*[:=]\s*(?:(?:bearer|basic)\s+)?\S+|"
    r"authorization\s+(?:(?:bearer|basic)\s+\S+|"
    r"(?!(?:policy|overview|authentication|auth|realm|challenge)\b)\S+)|"
    r"(?:password|passwd|token|secret|api[ _-]?key|cookie)\s+"
    r"(?!(?:rotation|policy|management)\b)\S+|"
    r"(?:bearer|basic)\s+"
    r"(?!(?:authentication|auth|realm|challenge)\b)\S+)",
    re.IGNORECASE,
)
_SPACE_PATTERN = re.compile(r"\s+")
_PROTOCOL_SCRIPT_VALUES = {
    "modbus-discover": "modbus",
    "smb-os-discovery": "smb",
}


@dataclass(slots=True)
class AssessmentResult:
    """Assessment output keyed by the host identity used in the payload."""

    machine_types: dict[str, MachineType]
    device_profiles: dict[str, DeviceProfilePayload]
    exposures: list[ExposurePayload]


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


def _safe_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    compact = _SPACE_PATTERN.sub(" ", value).strip()
    if not compact or _PRIVATE_KEY_PATTERN.search(compact):
        return None
    compact = _CREDENTIAL_PATTERN.sub("[REDACTED]", compact)
    if not compact.replace("[REDACTED]", "").strip(" ;,:|-/"):
        return None
    return compact[:limit]


def _evidence(
    kind: EvidenceKind, source: str, value: object
) -> AssessmentEvidencePayload | None:
    safe_source = _safe_text(source, MAX_EVIDENCE_SOURCE_CHARS)
    safe_value = _safe_text(value, MAX_EVIDENCE_VALUE_CHARS)
    if safe_source is None or safe_value is None:
        return None
    return AssessmentEvidencePayload(kind=kind, source=safe_source, value=safe_value)


def _bounded_evidence(
    evidence: Iterable[AssessmentEvidencePayload],
) -> list[AssessmentEvidencePayload]:
    unique: dict[tuple[str, str, str], AssessmentEvidencePayload] = {}
    for item in evidence:
        key = (item.kind, item.source, item.value.casefold())
        unique.setdefault(key, item)
    return sorted(
        unique.values(),
        key=lambda item: (item.kind, item.source, item.value),
    )[:MAX_EVIDENCE_ITEMS]


def _bounded_messages(values: Iterable[str], maximum: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        safe = _safe_text(value, MAX_REASON_CHARS)
        if safe is None or safe.casefold() in seen:
            continue
        seen.add(safe.casefold())
        result.append(safe)
    return sorted(result, key=str.casefold)[:maximum]


def _has_token(value: str, token: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", value) is not None


def _matching_type_tokens(value: str) -> set[MachineType]:
    lowered = value.casefold()
    matches: set[MachineType] = set()
    for machine_type, tokens in PRODUCT_TYPE_TOKENS.items():
        if machine_type != "unknown" and any(
            _has_token(lowered, token) for token in tokens
        ):
            matches.add(machine_type)
    return matches


def _is_locally_administered(mac: str | None) -> bool:
    if not mac:
        return False
    try:
        return bool(int(mac.split(":", 1)[0], 16) & 0x02)
    except (ValueError, IndexError):
        return False


def _port_evidence_key(port: PortInfo) -> tuple[object, ...]:
    """Return an order-independent key for assessment-relevant port evidence."""

    script_facts = tuple(
        sorted(
            _script_facts(port.scripts),
            key=lambda item: (item[0], item[1].casefold(), item[1]),
        )
    )
    cpes = tuple(
        sorted(port.service.cpes, key=lambda value: (value.casefold(), value))
    )
    richness = sum(
        bool(value)
        for value in (
            port.service.name,
            port.service.product,
            port.service.version,
            port.service.cpes,
            port.scripts,
        )
    )
    return (
        richness,
        port.service.name.casefold(),
        port.service.name,
        port.service.product.casefold(),
        port.service.product,
        port.service.version.casefold(),
        port.service.version,
        cpes,
        script_facts,
        _reports_unauthenticated_surface(port.scripts),
        port.protocol.casefold(),
        port.protocol,
    )


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
        (53 in ports or "domain" in names)
        and bool({80, 443, 8080} & ports)
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
    locally_administered = _is_locally_administered(host.mac)
    vendor = _safe_text(host.vendor, MAX_EVIDENCE_VALUE_CHARS)
    vendor_known = vendor is not None and vendor.casefold() != "unknown"
    manufacturer = None if locally_administered else vendor if vendor_known else None
    conflicts: list[str] = []
    limitations: list[str] = []
    product_values: list[_ProductFact] = []
    model_values: list[tuple[str, str]] = []
    supplemental_evidence: list[AssessmentEvidencePayload] = []

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
        for machine_type in _matching_type_tokens(hostname):
            signals.append(
                _Signal(
                    machine_type,
                    "hostname",
                    "discovery",
                    SIGNAL_WEIGHTS["hostname"],
                    _evidence("hostname", "discovery", hostname),  # type: ignore[arg-type]
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
            if candidates:
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
            script_evidence = _evidence(
                kind, endpoint, value  # type: ignore[arg-type]
            )
            if script_evidence:
                supplemental_evidence.append(script_evidence)
            candidates = _matching_type_tokens(value)
            signal_kind = "protocol" if kind == "protocol" else "product"
            weight = SIGNAL_WEIGHTS[signal_kind]
            for candidate in candidates:
                item = _evidence(kind, endpoint, value)  # type: ignore[arg-type]
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
                        kind,  # type: ignore[arg-type]
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
            conflicts.append(
                "Manufacturer evidence is tied: " + ", ".join(best) + "."
            )

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
        model_source, model = sorted(
            model_values, key=lambda item: (item[1], item[0])
        )[0]
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


def _script_facts(scripts: Iterable[ScriptResult]) -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    for script in sorted(scripts, key=lambda item: item.script_id):
        script_id = script.script_id.casefold().strip()
        protocol = _PROTOCOL_SCRIPT_VALUES.get(script_id)
        if protocol:
            facts.append(("protocol", protocol))
        if script_id == "http-title":
            title = _safe_text(script.output, MAX_EVIDENCE_VALUE_CHARS)
            if title:
                facts.append(("banner", title))
        if script_id == "ssl-cert" and isinstance(script.data, dict):
            for name in ("subject", "issuer"):
                raw_value = script.data.get(name)
                if isinstance(raw_value, dict):
                    raw_value = raw_value.get("commonName")
                value = (
                    _safe_text(
                        f"{name}: {raw_value}", MAX_EVIDENCE_VALUE_CHARS
                    )
                    if isinstance(raw_value, str)
                    else None
                )
                if value:
                    facts.append(("certificate", value))
    return facts


def _reports_unauthenticated_surface(scripts: Iterable[ScriptResult]) -> bool:
    for script in scripts:
        if script.script_id.casefold().strip() != "ftp-anon":
            continue
        output = script.output.casefold()
        reports_allowed = (
            "anonymous ftp login allowed" in output
            or "anonymous login allowed" in output
        )
        if reports_allowed:
            return True
    return False


def _roles_for_text(value: str, *, structured: bool) -> set[ExposureRole]:
    lowered = value.casefold()
    matches: set[ExposureRole] = set()
    for role, tokens in EXPOSURE_ROLE_TOKENS.items():
        if role in {"general_service", "unknown"}:
            continue
        if role in {"administration", "api"} and not structured:
            continue
        if any(_has_token(lowered, token) for token in tokens):
            matches.add(role)
    return matches


def _confirmed_industrial_services_for_endpoint(
    host: HostInfo, port: PortInfo
) -> list[ModbusService]:
    if port.protocol.casefold() != "tcp":
        return []
    return [
        service
        for service in host.industrial_services
        if service.port == port.port and service.confidence == "confirmed"
    ]


def _has_confirmed_industrial_identity(host: HostInfo, port: PortInfo) -> bool:
    return bool(_confirmed_industrial_services_for_endpoint(host, port))


def _select_role(
    host: HostInfo, port: PortInfo
) -> tuple[ExposureRole, ExposureConfidence, str]:
    if _has_confirmed_industrial_identity(host, port):
        return "device_control", "high", "confirmed industrial protocol identity"

    script_facts = _script_facts(port.scripts)
    protocol_roles: set[ExposureRole] = set()
    for kind, value in script_facts:
        if kind == "protocol":
            protocol_roles.update(_roles_for_text(value, structured=True))
    if len(protocol_roles) == 1:
        return next(iter(protocol_roles)), "high", "confirmed protocol evidence"
    if len(protocol_roles) > 1:
        return "unknown", "high", "contradictory confirmed protocol evidence"

    product_roles: set[ExposureRole] = set()
    for value in (*port.service.cpes, port.service.product):
        safe = _safe_text(value, MAX_EVIDENCE_VALUE_CHARS)
        if safe:
            product_roles.update(_roles_for_text(safe, structured=False))
    if len(product_roles) == 1:
        return next(iter(product_roles)), "medium", "product or CPE evidence"
    if len(product_roles) > 1:
        return "unknown", "medium", "contradictory product evidence"

    structured_roles: set[ExposureRole] = set()
    for kind, value in script_facts:
        if kind != "protocol":
            structured_roles.update(_roles_for_text(value, structured=True))
    if len(structured_roles) == 1:
        return next(iter(structured_roles)), "medium", "structured inspection evidence"
    if len(structured_roles) > 1:
        return "unknown", "medium", "contradictory structured evidence"

    service = _safe_text(port.service.name, MAX_EVIDENCE_VALUE_CHARS)
    product = _safe_text(port.service.product, MAX_EVIDENCE_VALUE_CHARS)
    service_roles: set[ExposureRole] = set()
    for value in (service, product):
        if value:
            service_roles.update(_roles_for_text(value, structured=False))
    if len(service_roles) == 1:
        return next(iter(service_roles)), "low", "observed service fingerprint"
    if len(service_roles) > 1:
        return "unknown", "low", "contradictory service fingerprint"

    port_roles = {
        role for role, ports in EXPOSURE_ROLE_PORTS.items() if port.port in ports
    }
    if len(port_roles) == 1:
        return next(iter(port_roles)), "low", "conservative port fallback"
    if len(port_roles) > 1:
        return "unknown", "low", "ambiguous port fallback"
    if service and service.casefold() != "unknown":
        return "general_service", "low", "identified open service"
    return "unknown", "low", "no reliable service fingerprint"


def _has_tls_evidence(port: PortInfo) -> bool:
    service_labels = (
        port.service.name,
        port.service.product,
        getattr(port.service, "tunnel", ""),
    )
    if any(
        _has_token(label.casefold(), token)
        for label in service_labels
        if label
        for token in ("https", "ssl", "tls")
    ):
        return True
    return any(
        script.script_id.casefold().startswith(("ssl-", "tls-"))
        for script in port.scripts
    )


def _is_cleartext_http(port: PortInfo) -> bool:
    service_name = port.service.name.casefold()
    if not _has_token(service_name, "http"):
        return False
    return not _has_tls_evidence(port)


def _has_cleartext_control_evidence(host: HostInfo, port: PortInfo) -> bool:
    if _has_tls_evidence(port):
        return False
    if _has_confirmed_industrial_identity(host, port):
        return True
    return any(
        kind == "protocol"
        and any(
            _has_token(value.casefold(), token)
            for token in PRIORITY_CLEARTEXT_TOKENS
        )
        for kind, value in _script_facts(port.scripts)
    )


def _exposure_for(host: HostInfo, port: PortInfo) -> ExposurePayload:
    role, confidence, basis = _select_role(host, port)
    observed_service = (
        _safe_text(port.service.name, MAX_EVIDENCE_VALUE_CHARS) or "unknown"
    )
    version_parts = [
        value
        for value in (
            _safe_text(port.service.product, MAX_EVIDENCE_VALUE_CHARS),
            _safe_text(port.service.version, MAX_EVIDENCE_VALUE_CHARS),
        )
        if value
    ]
    observed_version = _safe_text(
        " ".join(version_parts), MAX_EVIDENCE_VALUE_CHARS
    )
    if observed_version is None:
        observed_version = next(
            (
                safe_cpe
                for cpe in sorted(port.service.cpes, key=str.casefold)
                if (safe_cpe := _safe_text(cpe, MAX_EVIDENCE_VALUE_CHARS))
            ),
            None,
        )
    lowered = " ".join(
        value.casefold()
        for value in (
            observed_service,
            port.service.product,
            port.service.version,
            *port.service.cpes,
        )
        if value
    )
    cleartext_role = role in {
        "administration",
        "remote_access",
        "device_control",
    }
    cleartext_priority = cleartext_role and not _has_tls_evidence(port) and (
        any(_has_token(lowered, token) for token in PRIORITY_CLEARTEXT_TOKENS)
        or (role == "administration" and _is_cleartext_http(port))
        or (role == "device_control" and _has_cleartext_control_evidence(host, port))
    )
    unauthenticated_priority = _reports_unauthenticated_surface(port.scripts)
    attention: ExposureAttention
    if cleartext_priority or unauthenticated_priority:
        attention = "priority"
    elif role in REVIEW_ROLES:
        attention = "review"
    else:
        attention = "informational"

    evidence: list[AssessmentEvidencePayload] = []
    endpoint = f"{port.port}/{port.protocol}"
    for item in (
        _evidence("port", "nmap", f"{endpoint} open"),
        _evidence("service", endpoint, observed_service),
        _evidence("version", endpoint, observed_version),
    ):
        if item:
            evidence.append(item)
    for cpe in port.service.cpes:
        item = _evidence("cpe", endpoint, cpe)
        if item:
            evidence.append(item)
    for kind, value in _script_facts(port.scripts):
        item = _evidence(kind, "selected nse evidence", value)  # type: ignore[arg-type]
        if item:
            evidence.append(item)
    if unauthenticated_priority:
        item = _evidence(
            "protocol", "selected nse evidence", "anonymous FTP access reported"
        )
        if item:
            evidence.append(item)
    for _service in _confirmed_industrial_services_for_endpoint(host, port):
        item = _evidence("industrial", endpoint, "confirmed Modbus TCP identity")
        if item:
            evidence.append(item)

    role_label = role.replace("_", " ")
    if cleartext_priority:
        attention_clause = (
            "attention is priority because accepted evidence indicates a "
            f"cleartext {role_label} channel"
        )
    elif unauthenticated_priority:
        attention_clause = (
            "attention is priority because accepted evidence reports an "
            "unauthenticated sensitive surface"
        )
    elif attention == "review":
        attention_clause = (
            "attention is review because the "
            f"{role_label} role uses the review baseline"
        )
    else:
        attention_clause = (
            "attention is informational because the "
            f"{role_label} role uses the informational baseline"
        )
    reason = (
        f"The endpoint is classified as {role_label} from {basis}; "
        f"{attention_clause}."
    )
    return ExposurePayload(
        ip=host.ip,
        port=port.port,
        protocol=port.protocol if port.protocol in {"tcp", "udp"} else "tcp",
        observed_service=observed_service,
        observed_version=observed_version,
        role=role,
        attention=attention,
        confidence=confidence,
        reason=reason[:MAX_REASON_CHARS],
        evidence=_bounded_evidence(evidence),
    )


def _best_duplicate_port(ports: Iterable[PortInfo]) -> PortInfo:
    return max(ports, key=_port_evidence_key)


def assess_hosts(hosts: Iterable[HostInfo]) -> AssessmentResult:
    """Assess accepted host evidence without performing any I/O."""

    machine_types: dict[str, MachineType] = {}
    device_profiles: dict[str, DeviceProfilePayload] = {}
    exposures: list[ExposurePayload] = []
    ordered_hosts = sorted(hosts, key=lambda host: ip_address(host.ip))
    for host in ordered_hosts:
        machine_type, profile = _profile_host(host)
        machine_types[host.ip] = machine_type
        device_profiles[host.ip] = profile
        endpoints: dict[tuple[str, int], list[PortInfo]] = defaultdict(list)
        for port in host.ports:
            if port.state == "open":
                protocol = port.protocol if port.protocol in {"tcp", "udp"} else "tcp"
                endpoints[(protocol, port.port)].append(port)
        for endpoint in sorted(endpoints):
            port = _best_duplicate_port(endpoints[endpoint])
            exposures.append(_exposure_for(host, port))
    exposures.sort(key=lambda item: (int(item.ip), item.protocol, item.port))
    return AssessmentResult(machine_types, device_profiles, exposures)
