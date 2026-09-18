from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.core.config import Settings, get_settings
from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.errors import ApiError
from api.schemas.ai import AIChatHistoryResponse, AIChatRequest, AIChatResponse
from api.schemas.read import (
    HostDetailResponse,
    HostGroup,
    HostListResponse,
    HostSortBy,
    SortOrder,
)
from api.services.ai.chat import (
    build_host_context,
    finding_reference_map,
    list_chat_messages,
    save_chat_message,
)
from api.services.ai.groq import AIProviderError, ai_is_available, build_ai_provider
from api.services.ai.orchestrator import AIOrchestrator
from api.services.read import (
    DEFAULT_PAGE,
    DEFAULT_PER_PAGE,
    get_host_detail,
    list_findings,
    list_hosts,
)

router = APIRouter()


@router.get("/api/v1/hosts/{host_id}/explain", response_model=AIChatHistoryResponse)
def host_ai_history(
    host_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> AIChatHistoryResponse:
    host = get_host_detail(session, host_id, org_id=caller.org_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    latest_scan_id = host.scan_history[0].scan_id if host.scan_history else None
    if latest_scan_id is None:
        return AIChatHistoryResponse(data=[])
    return AIChatHistoryResponse(
        data=list_chat_messages(
            session,
            scan_id=latest_scan_id,
            org_id=caller.org_id,
            scope_type="host",
            scope_id=host_id,
        )
    )


@router.post(
    "/api/v1/hosts/{host_id}/explain",
    response_model=AIChatResponse,
    operation_id="explainHostWithAI",
)
def explain_host(
    host_id: UUID,
    payload: AIChatRequest,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AIChatResponse:
    if not ai_is_available(settings):
        raise ApiError(503, "The AI assistant is unavailable.", code="ai_unavailable")
    host = get_host_detail(session, host_id, org_id=caller.org_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    findings = list_findings(
        session, org_id=caller.org_id, host_id=host_id, per_page=100
    ).data
    provider = build_ai_provider(settings)
    assert provider is not None
    try:
        response = AIOrchestrator(provider).answer_question(
            context=build_host_context(host, findings),
            question=payload.question,
            finding_references=finding_reference_map(findings, payload.question),
        )
        latest_scan_id = host.scan_history[0].scan_id if host.scan_history else None
        if latest_scan_id is not None:
            save_chat_message(
                session,
                scan_id=latest_scan_id,
                user_id=caller.sub,
                question=payload.question,
                response=response,
                scope_type="host",
                scope_id=host_id,
        )
        return response
    except AIProviderError as exc:
        if exc.code == "provider_rate_limited":
            wait_seconds = exc.retry_after_seconds or 60
            raise ApiError(
                429,
                "Limite temporário de tokens da IA atingido. "
                f"Tente novamente em aproximadamente {wait_seconds} segundos.",
                code="ai_rate_limited",
            ) from exc
        raise ApiError(
            502,
            "The AI assistant could not explain this host.",
            code="ai_provider_error",
        ) from exc


@router.get("/api/v1/hosts", response_model=HostListResponse)
def read_hosts(
    page: int = Query(DEFAULT_PAGE, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=100),
    sort_by: HostSortBy = Query("last_seen_at"),
    sort_order: SortOrder = Query("desc"),
    group: HostGroup = Query("active"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> HostListResponse:
    return list_hosts(
        session,
        org_id=caller.org_id,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
        group=group,
    )


@router.get("/api/v1/hosts/{host_id}", response_model=HostDetailResponse)
def read_host(
    host_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> HostDetailResponse:
    host = get_host_detail(session, host_id, org_id=caller.org_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    return host
