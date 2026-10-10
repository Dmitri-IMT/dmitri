from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session

from api.schemas.ai import AILanguage, ScanAIAnalysisCompleted
from api.schemas.read import ScanDetailResponse, ScanRiskSummaryResponse
from api.schemas.reports import ReportKind, ScanReportResponse
from api.services.ai.jobs import get_scan_ai_analysis
from api.services.read import get_scan_detail, get_scan_risk_summary


class ReportNotReadyError(ValueError):
    pass


def build_scan_report(
    session: Session,
    scan_id: UUID,
    *,
    org_id: UUID,
    kind: ReportKind,
    ai_enabled: bool,
    language: AILanguage = "en",
    now: datetime | None = None,
) -> ScanReportResponse | None:
    detail = get_scan_detail(session, scan_id, org_id=org_id)
    if detail is None:
        return None
    if detail.status != "completed":
        raise ReportNotReadyError("scan must be completed before a report is generated")
    risk = get_scan_risk_summary(session, scan_id, org_id=org_id)
    if risk is None:
        raise ReportNotReadyError("risk summary is not available")
    analysis = get_scan_ai_analysis(
        session,
        scan_id,
        org_id=org_id,
        ai_enabled=ai_enabled,
        language=language,
    )
    generated_at = now or datetime.now(timezone.utc)
    sections = (
        _explained_sections(detail, risk, analysis, language)
        if kind == "explained"
        else _technical_sections(detail, risk, analysis)
    )
    return ScanReportResponse(
        scan_id=scan_id,
        kind=kind,
        language=language,
        generated_at=generated_at,
        filename=f"dmitri-scan-{scan_id}-{kind}.pdf",
        content_type="application/pdf",
        sections=sections,
    )


def _explained_sections(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    analysis: object,
    language: AILanguage,
) -> dict[str, Any]:
    completed = (
        analysis
        if isinstance(analysis, ScanAIAnalysisCompleted)
        else None
    )
    return {
        "overview": (
            completed.analysis.plain_language_summary
            if completed is not None
            else _fallback_overview(language, detail.host_count, detail.finding_count)
        ),
        "attention_level": _attention_level(risk),
        "what_to_do_first": (
            [
                action.model_dump(mode="json")
                for action in completed.analysis.priority_actions
            ]
            if completed is not None
            else [_fallback_action(language)]
        ),
        "limitations": (
            completed.analysis.uncertainties
            if completed is not None
            else [_fallback_limitation(language)]
        ),
    }


def _technical_sections(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    analysis: object,
) -> dict[str, Any]:
    return {
        "scan": detail.model_dump(mode="json"),
        "risk_summary": risk.model_dump(mode="json"),
        "ai_analysis": (
            analysis.model_dump(mode="json")
            if isinstance(analysis, ScanAIAnalysisCompleted)
            else None
        ),
    }


def _attention_level(risk: ScanRiskSummaryResponse) -> str:
    if risk.severity.critical:
        return "critical"
    if risk.severity.high:
        return "high"
    if risk.severity.medium:
        return "medium"
    if risk.severity.low:
        return "low"
    return "none"


def _fallback_overview(language: AILanguage, hosts: int, findings: int) -> str:
    return {
        "en": f"The scan observed {hosts} machines and {findings} vulnerabilities.",
        "pt-BR": (
            f"A varredura encontrou {hosts} equipamentos e "
            f"{findings} vulnerabilidades."
        ),
        "ru": f"Сканирование обнаружило устройств: {hosts}; уязвимостей: {findings}.",
    }[language]


def _fallback_action(language: AILanguage) -> str:
    return {
        "en": "Ask an IT professional to review the vulnerabilities.",
        "pt-BR": "Peça a um profissional de TI para revisar as vulnerabilidades.",
        "ru": "Попросите ИТ-специалиста проверить уязвимости.",
    }[language]


def _fallback_limitation(language: AILanguage) -> str:
    return {
        "en": "An AI explanation was not available for this scan.",
        "pt-BR": "A explicação da IA não está disponível para esta varredura.",
        "ru": "Объяснение ИИ для этого сканирования недоступно.",
    }[language]
