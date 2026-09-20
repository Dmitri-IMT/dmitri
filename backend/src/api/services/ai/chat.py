from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from api.models.persistence import AIChatMessageRecord, ScanRecord
from api.schemas.ai import (
    AIChatHistoryEntry,
    AIChatResponse,
    ProviderAIChatResponse,
)
from api.schemas.read import (
    FindingRead,
    HostDetailResponse,
    ScanDetailResponse,
    ScanRiskSummaryResponse,
)
from api.services.ai.context import (
    AI_CONTEXT_VERSION,
    AIFindingContext,
    assign_machine_ref,
    replace_ai_references,
)

MAX_CHAT_HISTORY = 10


@dataclass(frozen=True)
class AIChatContextBundle:
    provider_context: dict[str, object]
    finding_ids_by_ref: dict[str, UUID]
    display_values_by_ref: dict[str, str]


def build_scan_chat_bundle(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    question: str | None = None,
) -> AIChatContextBundle:
    """Build a placeholder-only scan context for interactive questions."""
    machine_refs = _collect_machine_refs(detail.findings)
    contexts, finding_ids_by_ref, display_values_by_ref = _finding_context_bundle(
        _select_findings(list(detail.findings), question),
        machine_refs,
    )
    _seed_machine_display_values(detail.findings, machine_refs, display_values_by_ref)
    return AIChatContextBundle(
        provider_context={
            "context_version": AI_CONTEXT_VERSION,
            "scope": "scan",
            "scan_mode": detail.scan_mode,
            "status": detail.status,
            "host_count": detail.host_count,
            "aggregate": {
                "total_findings": risk.total_findings,
                "scored_findings": risk.scored_findings,
                "confirmed_findings": risk.confirmed_findings,
                "kev_findings": risk.kev_findings,
                "average_risk_score": risk.average_risk_score,
                "max_risk_score": risk.max_risk_score,
                "severity": risk.severity.model_dump(mode="json"),
            },
            "top_findings": [item.model_dump(mode="json") for item in contexts],
            "machine_vulnerability_summary": _machine_vulnerability_summary(
                detail.findings, machine_refs
            ),
        },
        finding_ids_by_ref=finding_ids_by_ref,
        display_values_by_ref=display_values_by_ref,
    )


def build_finding_chat_bundle(finding: FindingRead) -> AIChatContextBundle:
    machine_refs: dict[UUID | None, str] = {}
    machine_ref = assign_machine_ref(machine_refs, finding.host_id)
    finding_ref = "finding_1"
    finding_ids_by_ref = {finding_ref: finding.finding_id}
    display_values_by_ref = {finding_ref: finding.title}
    if machine_ref is not None:
        display_values_by_ref[machine_ref] = (
            finding.host_hostname
            or str(finding.host_ip)
            or "the affected machine"
        )
    context = AIFindingContext(
        finding_ref=finding_ref,
        machine_ref=machine_ref,
        cve_id=finding.cve_id,
        cvss_score=finding.cvss_score,
        severity=finding.severity,
        confidence=finding.confidence,
        risk_score=finding.risk_score,
        exploitability=finding.exploitability,
        epss_score=None,
        epss_percentile=None,
        is_kev=False,
        known_ransomware=False,
    )
    return AIChatContextBundle(
        provider_context={
            "context_version": AI_CONTEXT_VERSION,
            "scope": "finding",
            "finding": context.model_dump(mode="json"),
        },
        finding_ids_by_ref=finding_ids_by_ref,
        display_values_by_ref=display_values_by_ref,
    )


def build_host_chat_bundle(
    host: HostDetailResponse, findings: list[FindingRead]
) -> AIChatContextBundle:
    machine_refs: dict[UUID | None, str] = {}
    machine_ref = assign_machine_ref(machine_refs, host.host_id)
    if machine_ref is None:
        machine_ref = "machine_1"
        machine_refs[host.host_id] = machine_ref
    display_values_by_ref = {
        machine_ref: host.hostname or str(host.ip) or "the affected machine"
    }
    contexts, finding_ids_by_ref, finding_display = _finding_context_bundle(
        findings[:10], machine_refs
    )
    display_values_by_ref.update(finding_display)
    service_refs: dict[int, str] = {}
    services = []
    for port in host.ports[:20]:
        service_ref = f"service_{len(service_refs) + 1}"
        service_refs[port.port] = service_ref
        display_values_by_ref[service_ref] = (
            f"{port.port}/{port.protocol} {port.service or 'unknown'}"
        )
        services.append(
            {
                "service_ref": service_ref,
                "protocol": port.protocol,
                "service": port.service,
            }
        )
    return AIChatContextBundle(
        provider_context={
            "context_version": AI_CONTEXT_VERSION,
            "scope": "host",
            "machine_ref": machine_ref,
            "machine_type": host.machine_type,
            "vulnerability_count": host.vulnerability_count,
            "highest_severity": host.highest_severity,
            "open_ports_count": host.open_ports_count,
            "services": services,
            "findings": [item.model_dump(mode="json") for item in contexts],
        },
        finding_ids_by_ref=finding_ids_by_ref,
        display_values_by_ref=display_values_by_ref,
    )


def answer_interactive_question(
    provider: Any,
    bundle: AIChatContextBundle,
    *,
    question: str,
    language: str = "en",
) -> AIChatResponse:
    provider_response = provider.answer_question(
        bundle.provider_context, question, language=language
    )
    if not isinstance(provider_response, ProviderAIChatResponse):
        provider_response = ProviderAIChatResponse.model_validate(provider_response)
    return materialize_chat_response(
        provider_response,
        bundle.finding_ids_by_ref,
        bundle.display_values_by_ref,
    )


def _collect_machine_refs(findings: list[object]) -> dict[UUID | None, str]:
    machine_refs: dict[UUID | None, str] = {}
    for finding in findings:
        assign_machine_ref(machine_refs, getattr(finding, "host_id", None))
    return machine_refs


def _seed_machine_display_values(
    findings: list[object],
    machine_refs: dict[UUID | None, str],
    display_values_by_ref: dict[str, str],
) -> None:
    for finding in findings:
        host_id = getattr(finding, "host_id", None)
        machine_ref = machine_refs.get(host_id)
        if machine_ref is None or machine_ref in display_values_by_ref:
            continue
        display_values_by_ref[machine_ref] = (
            getattr(finding, "host_hostname", None)
            or str(getattr(finding, "host_ip", "") or "")
            or "the affected machine"
        )


def _finding_context_bundle(
    findings: list[object],
    machine_refs: dict[UUID | None, str],
) -> tuple[list[AIFindingContext], dict[str, UUID], dict[str, str]]:
    finding_ids_by_ref: dict[str, UUID] = {}
    display_values_by_ref: dict[str, str] = {}
    contexts: list[AIFindingContext] = []
    for index, finding in enumerate(findings, start=1):
        finding_ref = f"finding_{index}"
        host_id = getattr(finding, "host_id", None)
        machine_ref = machine_refs.get(host_id)
        if machine_ref is None and host_id is not None:
            machine_ref = assign_machine_ref(machine_refs, host_id)
        finding_ids_by_ref[finding_ref] = finding.finding_id
        display_values_by_ref[finding_ref] = finding.title
        if machine_ref is not None:
            display_values_by_ref[machine_ref] = (
                getattr(finding, "host_hostname", None)
                or str(getattr(finding, "host_ip", "") or "")
                or "the affected machine"
            )
        contexts.append(
            AIFindingContext(
                finding_ref=finding_ref,
                machine_ref=machine_ref,
                cve_id=getattr(finding, "cve_id", None),
                cvss_score=getattr(finding, "cvss_score", None),
                severity=getattr(finding, "severity", "medium"),
                confidence=getattr(finding, "confidence", None),
                risk_score=getattr(finding, "risk_score", None),
                exploitability=getattr(finding, "exploitability", None),
                epss_score=None,
                epss_percentile=None,
                is_kev=False,
                known_ransomware=False,
            )
        )
    return contexts, finding_ids_by_ref, display_values_by_ref


def _machine_vulnerability_summary(
    findings: list[object],
    machine_refs: dict[UUID | None, str],
) -> list[dict[str, object]]:
    machines: dict[str, dict[str, object]] = {}
    for finding in findings:
        host_id = getattr(finding, "host_id", None)
        machine_ref = machine_refs.get(host_id)
        if machine_ref is None:
            continue
        entry = machines.setdefault(
            machine_ref,
            {
                "machine_ref": machine_ref,
                "finding_count": 0,
                "severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "max_risk_score": None,
            },
        )
        entry["finding_count"] = int(entry["finding_count"]) + 1
        severity = str(getattr(finding, "severity", "") or "").lower()
        severity_counts = entry["severity"]
        if isinstance(severity_counts, dict) and severity in severity_counts:
            severity_counts[severity] = int(severity_counts[severity]) + 1
        risk_score = getattr(finding, "risk_score", None)
        if risk_score is not None and (
            entry["max_risk_score"] is None or risk_score > entry["max_risk_score"]
        ):
            entry["max_risk_score"] = risk_score
    return sorted(
        machines.values(),
        key=lambda host: (-int(host["finding_count"]), str(host["machine_ref"])),
    )[:20]


_QUESTION_STOPWORDS = {
    "a", "as", "ao", "aos", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "essa", "este", "eu", "foi", "me", "na", "nas", "no", "nos",
    "o", "os", "para", "por", "que", "qual", "quando", "se", "sobre", "um",
    "uma", "vou", "é", "são",
}


def _select_findings(findings: list[object], question: str | None) -> list[object]:
    """Keep the bounded context while putting question-relevant findings first."""
    bounded = list(findings[:5])
    if not question or not bounded:
        return bounded
    terms = _question_terms(question)
    if not terms:
        return bounded

    ranked: list[tuple[int, int, object]] = []
    for index, finding in enumerate(bounded):
        searchable = " ".join(
            str(getattr(finding, field, "") or "")
            for field in (
                "title",
                "description",
                "recommendation",
                "service",
                "cve_id",
                "host_ip",
                "host_hostname",
            )
        )
        tokens = set(_question_terms(searchable))
        score = sum(term in tokens for term in terms)
        ranked.append((score, -index, finding))
    ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [finding for _, _, finding in ranked]


def _question_terms(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9._:-]*", normalized.lower())
        if len(token) >= 3 and token not in _QUESTION_STOPWORDS
    ]


def materialize_chat_response(
    response: ProviderAIChatResponse,
    finding_ids_by_ref: dict[str, UUID],
    display_values_by_ref: dict[str, str],
) -> AIChatResponse:
    unknown = set(response.referenced_finding_refs) - set(finding_ids_by_ref)
    if unknown:
        raise ValueError("chat response contains an unknown finding reference")
    return AIChatResponse(
        answer=replace_ai_references(response.answer, display_values_by_ref),
        uncertainties=[
            replace_ai_references(item, display_values_by_ref)
            for item in response.uncertainties
        ],
        referenced_finding_ids=[
            finding_ids_by_ref[reference]
            for reference in response.referenced_finding_refs
        ],
    )


def finding_reference_map(
    findings: list[object], question: str | None = None
) -> dict[str, UUID]:
    machine_refs = _collect_machine_refs(findings)
    _, finding_ids_by_ref, _ = _finding_context_bundle(
        _select_findings(findings, question), machine_refs
    )
    return finding_ids_by_ref


def save_chat_message(
    session: Session,
    *,
    scan_id: UUID,
    user_id: UUID,
    question: str,
    response: AIChatResponse,
    scope_type: str = "scan",
    scope_id: UUID | None = None,
    commit: bool = True,
) -> AIChatHistoryEntry:
    record = AIChatMessageRecord(
        scan_id=scan_id,
        user_id=user_id,
        scope_type=scope_type,
        scope_id=scope_id or scan_id,
        question=question,
        answer=response.answer,
        uncertainties_json=response.uncertainties,
        referenced_finding_ids_json=[
            str(item) for item in response.referenced_finding_ids
        ],
    )
    session.add(record)
    session.flush()
    session.refresh(record)
    older_records = session.exec(
        select(AIChatMessageRecord)
        .where(
            AIChatMessageRecord.scope_type == scope_type,
            AIChatMessageRecord.scope_id == (scope_id or scan_id),
        )
        .order_by(AIChatMessageRecord.created_at.desc())
        .offset(MAX_CHAT_HISTORY)
    ).all()
    for older_record in older_records:
        session.delete(older_record)
    if commit:
        session.commit()
    return _history_entry(record)


def list_chat_messages(
    session: Session,
    *,
    scan_id: UUID | None,
    org_id: UUID,
    scope_type: str = "scan",
    scope_id: UUID | None = None,
    limit: int = MAX_CHAT_HISTORY,
) -> list[AIChatHistoryEntry]:
    limit = min(limit, MAX_CHAT_HISTORY)
    filters = [
        ScanRecord.org_id == org_id,
        AIChatMessageRecord.scope_type == scope_type,
        AIChatMessageRecord.scope_id == (scope_id or scan_id),
    ]
    if scan_id is not None and scope_type != "host":
        filters.append(AIChatMessageRecord.scan_id == scan_id)
    statement = (
        select(AIChatMessageRecord)
        .join(ScanRecord, ScanRecord.scan_id == AIChatMessageRecord.scan_id)
        .where(*filters)
        .order_by(AIChatMessageRecord.created_at.desc())
        .limit(limit)
    )
    records = list(session.exec(statement).all())
    records.reverse()
    return [_history_entry(record) for record in records]


def _history_entry(record: AIChatMessageRecord) -> AIChatHistoryEntry:
    return AIChatHistoryEntry(
        message_id=record.message_id,
        question=record.question,
        answer=record.answer,
        uncertainties=record.uncertainties_json,
        referenced_finding_ids=[
            UUID(item) for item in record.referenced_finding_ids_json
        ],
        created_at=record.created_at,
    )
