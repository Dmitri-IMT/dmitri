from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session

from api.core.config import Settings, get_settings
from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent
from api.dependencies.auth import CallerIdentity, require_user
from api.errors import ApiError
from api.models.persistence import utc_now
from api.schemas.ai import (
    AIChatHistoryResponse,
    AIChatRequest,
    AIChatResponse,
    AILanguage,
    ScanAIAnalysisResponse,
)
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
from api.services.ai.chat import (
    build_chat_context,
    finding_reference_map,
    list_chat_messages,
    save_chat_message,
)
from api.services.ai.groq import (
    GROQ_PROVIDER_ID,
    AIProviderError,
    ai_is_available,
    build_ai_provider,
)
from api.services.ai.jobs import (
    AIAnalysisAlreadyRequestedError,
    get_scan_ai_analysis,
    request_scan_ai_analysis,
)
from api.services.ai.orchestrator import AIOrchestrator
from api.services.ai.telemetry import drain_provider_usage, persist_usage_events
from api.services.persistence import ScanClosedError, ScanOwnershipError, ingest_scan
from api.services.read import get_scan_detail, get_scan_risk_summary, list_scans
from api.services.report_pdf import render_scan_report_pdf
from api.services.reports import ReportNotReadyError, build_scan_report

router = APIRouter()


@router.get(
    "/api/v1/scans/{scan_id}/chat",
    response_model=AIChatHistoryResponse,
    operation_id="listScanAIChat",
)
def read_scan_ai_chat(
    scan_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> AIChatHistoryResponse:
    detail = get_scan_detail(session, scan_id, org_id=caller.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return AIChatHistoryResponse(
        data=list_chat_messages(session, scan_id=scan_id, org_id=caller.org_id)
    )


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
            provider_name=GROQ_PROVIDER_ID,
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


@router.post(
    "/api/v1/scans/{scan_id}/chat",
    response_model=AIChatResponse,
    operation_id="askScanAI",
)
def ask_scan_ai(
    scan_id: UUID,
    payload: AIChatRequest,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AIChatResponse:
    if not ai_is_available(settings):
        raise ApiError(503, "The AI assistant is unavailable.", code="ai_unavailable")
    detail = get_scan_detail(session, scan_id, org_id=caller.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if detail.status != "completed":
        raise ApiError(
            409, "The scan is not ready for questions.", code="scan_not_ready"
        )
    risk = get_scan_risk_summary(session, scan_id, org_id=caller.org_id)
    if risk is None:
        raise ApiError(409, "Risk summary is not available.", code="scan_not_ready")
    analysis = get_scan_ai_analysis(
        session, scan_id, org_id=caller.org_id, ai_enabled=True
    )
    provider = build_ai_provider(settings)
    assert provider is not None
    try:
        response = AIOrchestrator(provider).answer_question(
            context=build_chat_context(detail, risk, analysis, payload.question),
            question=payload.question,
            language=payload.language,
            finding_references=finding_reference_map(
                detail.findings if payload.question else risk.top_findings,
                payload.question,
            ),
        )
        persist_usage_events(
            session,
            drain_provider_usage(provider),
            scan_id=scan_id,
            org_id=caller.org_id,
            user_id=caller.sub,
        )
        save_chat_message(
            session,
            scan_id=scan_id,
            user_id=caller.sub,
            question=payload.question,
            response=response,
        )
        return response
    except (AIProviderError, ValueError) as exc:
        persist_usage_events(
            session,
            drain_provider_usage(provider),
            scan_id=scan_id,
            org_id=caller.org_id,
            user_id=caller.sub,
        )
        if (
            isinstance(exc, AIProviderError)
            and exc.code == "provider_context_too_large"
        ):
            raise ApiError(
                413,
                "O contexto deste scan é grande demais para uma pergunta. "
                "Tente uma pergunta mais específica.",
                code="ai_context_too_large",
            ) from exc
        if isinstance(exc, AIProviderError) and exc.code == "provider_rate_limited":
            wait_seconds = exc.retry_after_seconds or 60
            raise ApiError(
                429,
                "Limite temporário de tokens da IA atingido. "
                f"Tente novamente em aproximadamente {wait_seconds} segundos.",
                code="ai_rate_limited",
            ) from exc
        raise ApiError(
            502,
            "The AI assistant could not answer this question.",
            code="ai_provider_error",
        ) from exc


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
    return Response(
        content=render_scan_report_pdf(report),
        media_type=report.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{report.filename}"'
        },
    )
