from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlmodel import Session, select

from api.models.persistence import AIChatMessageRecord, ScanRecord
from api.schemas.ai import (
    AIChatHistoryEntry,
    AIChatResponse,
    ProviderAIChatResponse,
)
from api.schemas.read import (
    FindingEvidenceSummary,
    FindingRead,
    HostDetailResponse,
    ScanDetailResponse,
    ScanRiskSummaryResponse,
    SeverityBreakdown,
)
from api.services.ai.context import (
    AIChatContext,
    ChatAggregate,
    FindingChatContext,
    HostChatContext,
    MachineVulnerabilityCount,
    ScanChatContext,
    assign_machine_ref,
    build_finding_contexts,
    machine_display_value,
    reference_names,
    replace_ai_references,
    summarize_industrial_protocols,
)
from api.services.ai.groq import AIProviderError
from api.services.scan_evidence import (
    incomplete_check_count,
    summarize_finding_evidence,
)

MAX_CHAT_HISTORY = 10
MAX_CHAT_FINDINGS = 5
MAX_HOST_CHAT_FINDINGS = 10
MAX_MACHINE_SUMMARY_ROWS = 20


@runtime_checkable
class ChatProvider(Protocol):
    def answer_question(
        self, context: AIChatContext, question: str, *, language: str = "en"
    ) -> ProviderAIChatResponse: ...


@dataclass(frozen=True)
class AIChatContextBundle:
    provider_context: AIChatContext
    finding_ids_by_ref: dict[str, UUID]
    display_values_by_ref: dict[str, str]


def build_scan_chat_bundle(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    question: str | None = None,
) -> AIChatContextBundle:
    """Build a placeholder-only scan context for interactive questions."""
    machine_refs: dict[UUID | None, str] = {}
    for finding in detail.findings:
        assign_machine_ref(machine_refs, finding.host_id)
    bundle = build_finding_contexts(
        _rank_findings(detail.findings, question)[:MAX_CHAT_FINDINGS],
        machine_refs=machine_refs,
    )
    _seed_machine_display_values(
        detail.findings, machine_refs, bundle.display_values_by_ref
    )
    return AIChatContextBundle(
        provider_context=ScanChatContext(
            scan_mode=detail.scan_mode,
            status=detail.status,
            evidence_completeness=detail.evidence_completeness,
            incomplete_check_count=incomplete_check_count(detail.coverage),
            host_count=detail.host_count,
            aggregate=ChatAggregate(
                total_findings=risk.total_findings,
                scored_findings=risk.scored_findings,
                confirmed_findings=risk.confirmed_findings,
                kev_findings=risk.kev_findings,
                average_risk_score=risk.average_risk_score,
                max_risk_score=risk.max_risk_score,
                severity=risk.severity,
            ),
            top_findings=bundle.contexts,
            machine_vulnerability_summary=_machine_vulnerability_summary(
                detail.findings, machine_refs
            ),
            evidence_summary=detail.evidence_summary
            or FindingEvidenceSummary.model_validate(
                summarize_finding_evidence(detail.findings, scope="scan")
            ),
            industrial_protocols=summarize_industrial_protocols(
                service for host in detail.hosts
                for service in host.industrial_services
            ),
        ),
        finding_ids_by_ref=bundle.finding_ids_by_ref,
        display_values_by_ref=bundle.display_values_by_ref,
    )


def build_finding_chat_bundle(finding: FindingRead) -> AIChatContextBundle:
    machine_refs: dict[UUID | None, str] = {}
    bundle = build_finding_contexts([finding], machine_refs=machine_refs)
    return AIChatContextBundle(
        provider_context=FindingChatContext(
            finding=bundle.contexts[0],
            evidence_summary=FindingEvidenceSummary.model_validate(
                summarize_finding_evidence([finding], scope="filtered_findings")
            ),
        ),
        finding_ids_by_ref=bundle.finding_ids_by_ref,
        display_values_by_ref=bundle.display_values_by_ref,
    )


def build_host_chat_bundle(
    host: HostDetailResponse,
    findings: list[FindingRead],
    evidence_summary: FindingEvidenceSummary | None = None,
) -> AIChatContextBundle:
    machine_refs: dict[UUID | None, str] = {}
    machine_ref = assign_machine_ref(machine_refs, host.host_id)
    assert machine_ref is not None
    bundle = build_finding_contexts(
        findings[:MAX_HOST_CHAT_FINDINGS], machine_refs=machine_refs
    )
    bundle.display_values_by_ref.setdefault(
        machine_ref, machine_display_value(host.hostname, host.ip)
    )
    return AIChatContextBundle(
        provider_context=HostChatContext(
            machine_ref=machine_ref,
            machine_type=host.machine_type,
            vulnerability_count=host.vulnerability_count,
            highest_severity=host.highest_severity,
            open_ports_count=host.open_ports_count,
            findings=bundle.contexts,
            evidence_summary=evidence_summary
            or FindingEvidenceSummary.model_validate(
                summarize_finding_evidence(
                    findings, scope="filtered_findings"
                )
            ),
            industrial_protocols=summarize_industrial_protocols(
                host.industrial_services
            ),
        ),
        finding_ids_by_ref=bundle.finding_ids_by_ref,
        display_values_by_ref=bundle.display_values_by_ref,
    )


def answer_interactive_question(
    provider: ChatProvider,
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


def _seed_machine_display_values(
    findings: list[FindingRead],
    machine_refs: dict[UUID | None, str],
    display_values_by_ref: dict[str, str],
) -> None:
    for finding in findings:
        machine_ref = machine_refs.get(finding.host_id)
        if machine_ref is None or machine_ref in display_values_by_ref:
            continue
        display_values_by_ref[machine_ref] = machine_display_value(
            finding.host_hostname, finding.host_ip
        )


def _machine_vulnerability_summary(
    findings: list[FindingRead],
    machine_refs: dict[UUID | None, str],
) -> list[MachineVulnerabilityCount]:
    counts: dict[str, MachineVulnerabilityCount] = {}
    for finding in findings:
        machine_ref = machine_refs.get(finding.host_id)
        if machine_ref is None:
            continue
        entry = counts.setdefault(
            machine_ref,
            MachineVulnerabilityCount(
                machine_ref=machine_ref,
                finding_count=0,
                severity=SeverityBreakdown(),
            ),
        )
        entry.finding_count += 1
        severity = str(finding.severity).lower()
        if hasattr(entry.severity, severity):
            setattr(entry.severity, severity, getattr(entry.severity, severity) + 1)
        if finding.risk_score is not None and (
            entry.max_risk_score is None or finding.risk_score > entry.max_risk_score
        ):
            entry.max_risk_score = finding.risk_score
    return sorted(
        counts.values(),
        key=lambda entry: (-entry.finding_count, entry.machine_ref),
    )[:MAX_MACHINE_SUMMARY_ROWS]


_QUESTION_STOPWORDS = {
    "a", "as", "ao", "aos", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "essa", "este", "eu", "foi", "me", "na", "nas", "no", "nos",
    "o", "os", "para", "por", "que", "qual", "quando", "se", "sobre", "um",
    "uma", "vou", "é", "são",
}


def _rank_findings(
    findings: list[FindingRead], question: str | None
) -> list[FindingRead]:
    """Order the scan's findings so the question-relevant ones survive the cut."""
    terms = _question_terms(question) if question else []
    if not terms:
        return list(findings)

    def score(finding: FindingRead) -> int:
        searchable = " ".join(
            str(value or "")
            for value in (
                finding.title,
                finding.description,
                finding.recommendation,
                finding.service,
                finding.cve_id,
                finding.host_ip,
                finding.host_hostname,
            )
        )
        tokens = set(_question_terms(searchable))
        return sum(term in tokens for term in terms)

    ranked = [
        (score(finding), -index, finding) for index, finding in enumerate(findings)
    ]
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
    """Resolve provider placeholders, rejecting any reference we did not send."""
    used = set(response.referenced_finding_refs)
    for text in (response.answer, *response.uncertainties):
        used.update(reference_names(text))
    unknown = used - set(finding_ids_by_ref) - set(display_values_by_ref)
    if unknown:
        raise AIProviderError("invalid_provider_response", retryable=True)
    if set(response.referenced_finding_refs) - set(finding_ids_by_ref):
        raise AIProviderError("invalid_provider_response", retryable=True)
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
