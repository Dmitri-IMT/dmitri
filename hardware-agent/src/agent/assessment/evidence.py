"""Shared evidence normalization for local assessment."""

from __future__ import annotations

import re
from typing import Iterable

from agent.normalize.contracts import AssessmentEvidencePayload
from agent.scanner.models import PortInfo, ScriptResult

from .policy import (
    EXPOSURE_ROLE_TOKENS,
    MAX_EVIDENCE_ITEMS,
    MAX_EVIDENCE_SOURCE_CHARS,
    MAX_EVIDENCE_VALUE_CHARS,
    MAX_REASON_CHARS,
    PRODUCT_TYPE_TOKENS,
    EvidenceKind,
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


def _script_facts(scripts: Iterable[ScriptResult]) -> list[tuple[EvidenceKind, str]]:
    facts: list[tuple[EvidenceKind, str]] = []
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
                    _safe_text(f"{name}: {raw_value}", MAX_EVIDENCE_VALUE_CHARS)
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


def _port_evidence_key(port: PortInfo) -> tuple[object, ...]:
    """Return an order-independent key for assessment-relevant port evidence."""

    script_facts = tuple(
        sorted(
            _script_facts(port.scripts),
            key=lambda item: (item[0], item[1].casefold(), item[1]),
        )
    )
    cpes = tuple(sorted(port.service.cpes, key=lambda value: (value.casefold(), value)))
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
