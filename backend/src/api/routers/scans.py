from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session

from api.core.config import Settings, get_settings
from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent
from api.dependencies.auth import CallerIdentity, require_admin_row, require_user
from api.errors import ApiError
from api.models.identity import User
from api.models.persistence import utc_now
from api.schemas.ai import AILanguage, ScanAIAnalysisResponse
from api.schemas.deletion import ScanDeletionResponse
from api.schemas.read import (
    ScanDetailResponse,
    ScanListResponse,
    ScanRiskSummaryResponse,
    ScanSortBy,
    ScanStatus,
    SortOrder,
)
from api.schemas.reports import ReportKind, ScanReportResponse
from api.schemas.scan import ScanIngestAcceptedResponse, ScanIngestRequest
from api.services.ai.jobs import (
    AIAnalysisAlreadyRequestedError,
    get_scan_ai_analysis,
    request_scan_ai_analysis,
)
from api.services.ai.openai_responses import OPENAI_PROVIDER_ID, ai_is_available
from api.services.deletion import ScanRunningError, delete_all_scans, delete_scan
from api.services.persistence import ScanClosedError, ScanOwnershipError, ingest_scan
from api.services.read import get_scan_detail, get_scan_risk_summary, list_scans
from api.services.report_pdf import render_scan_report_pdf
from api.services.reports import ReportNotReadyError, build_scan_report

router = APIRouter()


@router.post(
    "/api/v1/scans",
    response_model=ScanIngestAcceptedResponse,
    status_code=202,
    operation_id="ingestScan",
)
def ingest_scan_route(
    payload: ScanIngestRequest,
    identity: AgentIdentity = Depends(require_agent),
    session: Session = Depends(get_session),
) -> ScanIngestAcceptedResponse:
    try:
        ingest_scan(session, payload, identity=identity, now=utc_now())
    except ScanOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except ScanClosedError as exc:
        raise HTTPException(
            status_code=400, detail="Scan is no longer accepting results"
        ) from exc

    return ScanIngestAcceptedResponse(
        message="scan received successfully",
        scan_id=payload.scan_id,
        hosts_received=len(payload.hosts),
        status="accepted",
    )


@router.get("/api/v1/scans", response_model=ScanListResponse)
def read_scans(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: ScanStatus | None = Query(None),
    agent_id: UUID | None = Query(None),
    sort_by: ScanSortBy = Query("timestamp"),
    sort_order: SortOrder = Query("desc"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> ScanListResponse:
    return list_scans(
        session,
        org_id=caller.org_id,
        page=page,
        per_page=per_page,
        status=status,
        agent_id=agent_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/api/v1/scans/{scan_id}", response_model=ScanDetailResponse)
def read_scan(
    scan_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> ScanDetailResponse:
    scan = get_scan_detail(session, scan_id, org_id=caller.org_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.delete(
    "/api/v1/scans",
    response_model=ScanDeletionResponse,
    operation_id="deleteAllScans",
)
def delete_all_scans_route(
    actor: User = Depends(require_admin_row),
    session: Session = Depends(get_session),
) -> ScanDeletionResponse:
    result = delete_all_scans(session, org_id=actor.org_id, actor=actor)
    return ScanDeletionResponse(
        deleted=result.deleted,
        skipped=result.skipped,
        machines_removed=result.machines_removed,
    )


@router.delete(
    "/api/v1/scans/{scan_id}", status_code=204, operation_id="deleteScan"
)
def delete_scan_route(
    scan_id: UUID,
    actor: User = Depends(require_admin_row),
    session: Session = Depends(get_session),
) -> None:
    try:
        deleted = delete_scan(
            session, scan_id=scan_id, org_id=actor.org_id, actor=actor
        )
    except ScanRunningError as exc:
        raise ApiError(
            409, "Stop the scan before you delete it.", code="scan_running"
        ) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Scan not found")


@router.get(
    "/api/v1/scans/{scan_id}/risk-summary",
    response_model=ScanRiskSummaryResponse,
    operation_id="getScanRiskSummary",
)
def read_scan_risk_summary(
    scan_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> ScanRiskSummaryResponse:
    summary = get_scan_risk_summary(session, scan_id, org_id=caller.org_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return summary


@router.get(
    "/api/v1/scans/{scan_id}/analysis",
    response_model=ScanAIAnalysisResponse,
    operation_id="getScanAIAnalysis",
)
def read_scan_ai_analysis(
    scan_id: UUID,
    language: AILanguage = Query("en"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> ScanAIAnalysisResponse:
    analysis = get_scan_ai_analysis(
        session,
        scan_id,
        org_id=caller.org_id,
        ai_enabled=ai_is_available(settings),
        language=language,
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return analysis


@router.post(
    "/api/v1/scans/{scan_id}/analysis",
    response_model=ScanAIAnalysisResponse,
    status_code=202,
    operation_id="requestScanAIAnalysis",
)
def request_scan_ai_analysis_route(
    scan_id: UUID,
    language: AILanguage = Query("en"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> ScanAIAnalysisResponse:
    try:
        analysis = request_scan_ai_analysis(
            session,
            scan_id,
            org_id=caller.org_id,
            ai_enabled=ai_is_available(settings),
            provider_name=OPENAI_PROVIDER_ID,
            model=settings.ai_model,
            language=language,
        )
    except AIAnalysisAlreadyRequestedError as exc:
        raise ApiError(
            409,
            "An analysis has already been requested for this scan.",
            code="analysis_already_requested",
        ) from exc
    if analysis is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return analysis


@router.get(
    "/api/v1/scans/{scan_id}/reports/{kind}",
    response_model=ScanReportResponse,
    operation_id="getScanReport",
)
def read_scan_report(
    scan_id: UUID,
    kind: ReportKind,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
    language: AILanguage = Query("en"),
) -> ScanReportResponse:
    try:
        report = build_scan_report(
            session,
            scan_id,
            org_id=caller.org_id,
            kind=kind,
            language=language,
            ai_enabled=ai_is_available(settings),
        )
    except ReportNotReadyError as exc:
        raise ApiError(
            409,
            "The scan is not ready for a report.",
            code="report_not_ready",
        ) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return report


@router.get(
    "/api/v1/scans/{scan_id}/reports/{kind}/download",
    response_class=Response,
    operation_id="downloadScanReport",
)
def download_scan_report(
    scan_id: UUID,
    kind: ReportKind,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
    language: AILanguage = Query("en"),
) -> Response:
    report = read_scan_report(
        scan_id, kind, session, caller, settings, language=language
    )
    content = (
        report.model_dump_json(indent=2)
        if kind == "technical"
        else render_scan_report_pdf(report)
    )
    return Response(
        content=content,
        media_type=report.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{report.filename}"'
        },
    )
