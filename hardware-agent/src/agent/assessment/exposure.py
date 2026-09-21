"""Exposure classification and targeted observation enrichment."""

from __future__ import annotations

from agent.normalize.contracts import AssessmentEvidencePayload, ExposurePayload
from agent.ot.modbus.models import ModbusService
from agent.scanner.models import HostInfo, PortInfo
from agent.targeted.models import TargetedObservation

from .evidence import (
    _bounded_evidence,
    _evidence,
    _has_token,
    _reports_unauthenticated_surface,
    _roles_for_text,
    _safe_text,
    _script_facts,
)
from .policy import (
    EXPOSURE_ROLE_PORTS,
    MAX_EVIDENCE_VALUE_CHARS,
    MAX_REASON_CHARS,
    PRIORITY_CLEARTEXT_TOKENS,
    REVIEW_ROLES,
    ExposureAttention,
    ExposureConfidence,
    ExposureRole,
)


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
            _has_token(value.casefold(), token) for token in PRIORITY_CLEARTEXT_TOKENS
        )
        for kind, value in _script_facts(port.scripts)
    )


def _targeted_endpoint_observations(
    host: HostInfo, port: PortInfo
) -> list[TargetedObservation]:
    return [
        observation
        for result in host.targeted_results
        if result.unit.ip == host.ip
        and result.unit.port == port.port
        and result.unit.protocol == port.protocol
        for observation in result.observations
    ]


def _targeted_web_evidence(
    observation: TargetedObservation,
) -> AssessmentEvidencePayload | None:
    if observation.kind not in {"administration", "api_surface"}:
        return None
    if (
        observation.path is None
        or observation.rule_id is None
        or observation.policy_version is None
    ):
        return None
    return _evidence(
        "web_path",
        f"ffuf:{observation.rule_id}@{observation.policy_version}",
        observation.path,
    )


def _exposure_for(host: HostInfo, port: PortInfo) -> ExposurePayload:
    role, confidence, basis = _select_role(host, port)
    targeted_observations = _targeted_endpoint_observations(host, port)
    targeted_roles = {
        "administration" if item.kind == "administration" else "api"
        for item in targeted_observations
        if item.kind in {"administration", "api_surface"}
    }
    if len(targeted_roles) == 1:
        role = next(iter(targeted_roles))  # type: ignore[assignment]
        confidence = "high"
        basis = "validated targeted web-surface observation"
    elif len(targeted_roles) > 1:
        role = "unknown"
        confidence = "high"
        basis = "contradictory targeted web-surface observations"
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
    observed_version = _safe_text(" ".join(version_parts), MAX_EVIDENCE_VALUE_CHARS)
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
    cleartext_priority = (
        cleartext_role
        and not _has_tls_evidence(port)
        and (
            any(_has_token(lowered, token) for token in PRIORITY_CLEARTEXT_TOKENS)
            or (role == "administration" and _is_cleartext_http(port))
            or (
                role == "device_control" and _has_cleartext_control_evidence(host, port)
            )
        )
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
        item = _evidence(kind, "selected nse evidence", value)
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
    for observation in targeted_observations:
        item = _targeted_web_evidence(observation)
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
