from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session

from api.schemas.ai import ScanAIAnalysisCompleted
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
    )
    generated_at = now or datetime.now(timezone.utc)
    sections = (
        _explained_sections(detail, risk, analysis)
        if kind == "explained"
        else _technical_sections(detail, risk, analysis)
    )
    return ScanReportResponse(
        scan_id=scan_id,
        kind=kind,
        generated_at=generated_at,
        filename=f"dmitri-scan-{scan_id}-{kind}.json",
        content_type="application/json",
        sections=sections,
    )


def _explained_sections(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    analysis: object,
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
            else f"The scan observed {detail.host_count} machines and "
            f"{detail.finding_count} vulnerabilities."
        ),
        "attention_level": _attention_level(risk),
        "what_to_do_first": (
            [
                action.model_dump(mode="json")
                for action in completed.analysis.priority_actions
            ]
            if completed is not None
            else ["Ask an IT professional to review the vulnerabilities."]
        ),
        "limitations": (
            completed.analysis.uncertainties
            if completed is not None
            else ["An AI explanation was not available for this scan."]
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
