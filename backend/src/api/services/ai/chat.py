from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlmodel import Session, select

from api.models.persistence import AIChatMessageRecord, ScanRecord
from api.schemas.ai import AIChatHistoryEntry, AIChatResponse
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
    AIFindingContext,
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
)
from api.services.ai.openai_responses import AIProviderError, ProviderChatAnswer
from api.services.ai.research import clean_source_url
from api.services.scan_evidence import (
    incomplete_check_count,
    summarize_finding_evidence,
)

MAX_CHAT_HISTORY = 10
MAX_CHAT_FINDINGS = 5
MAX_HOST_CHAT_FINDINGS = 10
MAX_MACHINE_SUMMARY_ROWS = 20
REMOVED_SECRET = "[removed]"

_NAMED_SECRET = re.compile(
    r"\b(password|passwd|pwd|senha|пароль|api[_ -]?key|token|secret)"
    r"(\s*[:=]\s*)\S+",
    re.IGNORECASE,
)
_TOKEN_PATTERNS = (
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"),
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
_ADDRESS_PATTERNS = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b"),
    re.compile(r"\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", re.IGNORECASE),
    re.compile(
        r"(?<![\w:])[0-9a-f]{0,4}(?::[0-9a-f]{0,4}){2,7}(?![\w:])",
        re.IGNORECASE,
    ),
)
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9+/_=-]{32,}\b")
_WRAPPED_LINK = re.compile(r"\(\s*!?\[[^\]]*\]\([^)]*\)\s*\)")
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_RAW_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HTML_TAG = re.compile(r"</?[a-z][^>]*>", re.IGNORECASE)
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_EMPTY_PARENS = re.compile(r"\(\s*\)")


@runtime_checkable
class ChatProvider(Protocol):
    def answer_question(
        self, context: AIChatContext, question: str, *, language: str = "en"
    ) -> ProviderChatAnswer: ...


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
        ),
        finding_ids_by_ref=bundle.finding_ids_by_ref,
        display_values_by_ref=bundle.display_values_by_ref,
    )


def context_findings(context: AIChatContext) -> list[AIFindingContext]:
    if isinstance(context, ScanChatContext):
        return context.top_findings
    if isinstance(context, HostChatContext):
        return context.findings
    return [context.finding]


def answer_interactive_question(
    provider: ChatProvider,
    bundle: AIChatContextBundle,
    *,
    question: str,
    language: str = "en",
) -> AIChatResponse:
    answer = provider.answer_question(
        bundle.provider_context, scrub_secrets(question), language=language
    )
    return materialize_chat_response(
        answer,
        bundle.finding_ids_by_ref,
        bundle.display_values_by_ref,
    )


def scrub_secrets(value: str, *, addresses: bool = True) -> str:
    text = _NAMED_SECRET.sub(rf"\1\2{REMOVED_SECRET}", value)
    for pattern in (*_TOKEN_PATTERNS, *(_ADDRESS_PATTERNS if addresses else ())):
        text = pattern.sub(_address_or_token_removed, text)
    return _LONG_TOKEN.sub(_mixed_token_removed, text)


def _address_or_token_removed(match: re.Match[str]) -> str:
    value = match.group(0)
    if value.count(":") >= 2 and "." not in value:
        if "::" not in value and value.count(":") < 5:
            return value
    return REMOVED_SECRET


def _mixed_token_removed(match: re.Match[str]) -> str:
    token = match.group(0)
    if re.search(r"\d", token) and re.search(r"[A-Za-z]", token):
        return REMOVED_SECRET
    return token


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


@dataclass(frozen=True)
class _AnswerSegment:
    text: str
    url: str | None = None


def materialize_chat_response(
    answer: ProviderChatAnswer,
    finding_ids_by_ref: dict[str, UUID],
    display_values_by_ref: dict[str, str],
) -> AIChatResponse:
    """Build the answer text, keeping only links the provider cited and consulted."""
    segments = _answer_segments(answer)
    used = [
        reference
        for segment in segments
        if segment.url is None
        for reference in reference_names(segment.text)
    ]
    if set(used) - set(finding_ids_by_ref) - set(display_values_by_ref):
        raise AIProviderError("invalid_provider_response", retryable=True)
    safe_values = {
        reference: value.translate(_MARKUP_FREE)
        for reference, value in display_values_by_ref.items()
    }
    text = "".join(
        replace_ai_references(segment.text, safe_values)
        if segment.url is None
        else f"[{_source_label(segment.url)}]({_link_target(segment.url)})"
        for segment in segments
    )
    text = _tidy(_EMPTY_PARENS.sub("", text))
    if len(text) < 3:
        raise AIProviderError("invalid_provider_response", retryable=False)
    return AIChatResponse(
        answer=text,
        uncertainties=[],
        referenced_finding_ids=[
            finding_ids_by_ref[reference]
            for reference in dict.fromkeys(used)
            if reference in finding_ids_by_ref
        ],
    )


_MARKUP_FREE = str.maketrans({"[": "(", "]": ")", "*": None})


def _answer_segments(answer: ProviderChatAnswer) -> list[_AnswerSegment]:
    consulted = {clean_source_url(url) for url in answer.sources} - {None}
    segments: list[_AnswerSegment] = []
    for part in answer.parts:
        cursor = 0
        for citation in sorted(part.citations, key=lambda item: item.start):
            if (
                citation.start < cursor
                or citation.start >= citation.end
                or citation.end > len(part.text)
            ):
                continue
            segments.append(
                _AnswerSegment(_clean_answer_text(part.text[cursor : citation.start]))
            )
            url = clean_source_url(citation.url)
            if url in consulted:
                segments.append(_AnswerSegment("", url))
            cursor = citation.end
        segments.append(_AnswerSegment(_clean_answer_text(part.text[cursor:])))
    return segments


def _clean_answer_text(value: str) -> str:
    text = _WRAPPED_LINK.sub("", value)
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _RAW_URL.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _HEADING.sub("", text).replace("`", "")
    return scrub_secrets(text, addresses=False)


def _tidy(text: str) -> str:
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _source_label(url: str) -> str:
    host = url.split("://", 1)[1].split("/", 1)[0]
    return host.removeprefix("www.")


def _link_target(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


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
