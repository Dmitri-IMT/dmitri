from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from sqlmodel import Session, select

from api.models.persistence import AIChatMessageRecord, ScanRecord
from api.schemas.ai import AIChatHistoryEntry, AIChatResponse, ProviderAIChatResponse
from api.schemas.read import ScanDetailResponse, ScanRiskSummaryResponse


def build_chat_context(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    analysis: object | None,
    question: str | None = None,
) -> dict[str, object]:
    """Build a bounded, read-only context for one scan question."""
    completed_analysis = getattr(analysis, "analysis", None)
    analysis_context = None
    if completed_analysis is not None:
        analysis_context = {
            "plain_language_summary": _clip(
                completed_analysis.plain_language_summary, 1200
            ),
            "overall_assessment": _clip(completed_analysis.overall_assessment, 1200),
            "priority_actions": [
                {
                    "priority": action.priority,
                    "title": _clip(action.title, 180),
                    "description": _clip(action.description, 400),
                }
                for action in completed_analysis.priority_actions[:5]
            ],
            "uncertainties": [
                _clip(item, 400) for item in completed_analysis.uncertainties[:5]
            ],
        }

    candidates = detail.findings if question else risk.top_findings
    if not candidates:
        candidates = risk.top_findings
    selected_findings = _select_findings(candidates, question)
    return {
        "scan": {
            "scan_id": str(detail.scan_id),
            "timestamp": detail.timestamp.isoformat(),
            "subnet": detail.subnet,
            "scan_mode": detail.scan_mode,
            "status": detail.status,
            "host_count": detail.host_count,
            "finding_count": detail.finding_count,
        },
        "risk_summary": {
            "total_findings": risk.total_findings,
            "scored_findings": risk.scored_findings,
            "confirmed_findings": risk.confirmed_findings,
            "kev_findings": risk.kev_findings,
            "average_risk_score": risk.average_risk_score,
            "max_risk_score": risk.max_risk_score,
            "severity": risk.severity.model_dump(mode="json"),
        },
        "host_vulnerability_summary": _host_vulnerability_summary(
            detail.findings
        ),
        "top_findings": [
            {
                "finding_ref": f"finding_{index}",
                "finding_id": str(finding.finding_id),
                "title": _clip(finding.title, 180),
                "description": _clip(finding.description, 500),
                "recommendation": _clip(finding.recommendation, 500),
                "severity": finding.severity,
                "cve_id": finding.cve_id,
                "cvss_score": finding.cvss_score,
                "risk_score": finding.risk_score,
                "host_ip": str(finding.host_ip) if finding.host_ip else None,
                "host_hostname": finding.host_hostname,
                "port": finding.port,
                "service": finding.service,
            }
            for index, finding in enumerate(selected_findings, start=1)
        ],
        "existing_ai_analysis": analysis_context,
    }


def _host_vulnerability_summary(findings: list[object]) -> list[dict[str, object]]:
    """Provide deterministic per-host totals for questions about equipment."""
    hosts: dict[str, dict[str, object]] = {}
    for finding in findings:
        ip = str(getattr(finding, "host_ip", "") or "")
        hostname = str(getattr(finding, "host_hostname", "") or "")
        key = ip or hostname or "unknown"
        entry = hosts.setdefault(
            key,
            {
                "host_ip": ip or None,
                "host_hostname": hostname or None,
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
        hosts.values(),
        key=lambda host: (-int(host["finding_count"]), str(host["host_ip"] or "")),
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


def _clip(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"


def materialize_chat_response(
    response: ProviderAIChatResponse,
    finding_ids_by_ref: dict[str, UUID],
) -> AIChatResponse:
    unknown = set(response.referenced_finding_refs) - set(finding_ids_by_ref)
    if unknown:
        raise ValueError("chat response contains an unknown finding reference")
    return AIChatResponse(
        answer=response.answer,
        uncertainties=response.uncertainties,
        referenced_finding_ids=[
            finding_ids_by_ref[reference]
            for reference in response.referenced_finding_refs
        ],
    )


def finding_reference_map(
    findings: list[object], question: str | None = None
) -> dict[str, UUID]:
    return {
        f"finding_{index}": finding.finding_id
        for index, finding in enumerate(_select_findings(findings, question), start=1)
    }


def save_chat_message(
    session: Session,
    *,
    scan_id: UUID,
    user_id: UUID,
    question: str,
    response: AIChatResponse,
) -> AIChatHistoryEntry:
    record = AIChatMessageRecord(
        scan_id=scan_id,
        user_id=user_id,
        question=question,
        answer=response.answer,
        uncertainties_json=response.uncertainties,
        referenced_finding_ids_json=[
            str(item) for item in response.referenced_finding_ids
        ],
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _history_entry(record)


def list_chat_messages(
    session: Session, *, scan_id: UUID, org_id: UUID, limit: int = 50
) -> list[AIChatHistoryEntry]:
    statement = (
        select(AIChatMessageRecord)
        .join(ScanRecord, ScanRecord.scan_id == AIChatMessageRecord.scan_id)
        .where(AIChatMessageRecord.scan_id == scan_id, ScanRecord.org_id == org_id)
        .order_by(AIChatMessageRecord.created_at)
        .limit(limit)
    )
    return [_history_entry(record) for record in session.exec(statement).all()]


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
