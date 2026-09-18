from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.core.config import Settings, get_settings
from api.core.severity import Severity
from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.errors import ApiError
from api.schemas.ai import AIChatHistoryResponse, AIChatRequest, AIChatResponse
from api.schemas.read import FindingListResponse, FindingRead
from api.services.ai.chat import (
    build_finding_context,
    finding_reference_map,
    list_chat_messages,
    save_chat_message,
)
from api.services.ai.groq import AIProviderError, ai_is_available, build_ai_provider
from api.services.ai.orchestrator import AIOrchestrator
from api.services.read import get_finding_detail, list_findings

router = APIRouter()


@router.get(
    "/api/v1/findings/{finding_id}/explain",
    response_model=AIChatHistoryResponse,
)
def finding_ai_history(
    finding_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> AIChatHistoryResponse:
    finding = get_finding_detail(session, finding_id, org_id=caller.org_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return AIChatHistoryResponse(
        data=list_chat_messages(
            session,
            scan_id=finding.scan_id,
            org_id=caller.org_id,
            scope_type="finding",
            scope_id=finding_id,
        )
    )


@router.post(
    "/api/v1/findings/{finding_id}/explain",
    response_model=AIChatResponse,
    operation_id="explainFindingWithAI",
)
def explain_finding(
    finding_id: UUID,
    payload: AIChatRequest,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AIChatResponse:
    if not ai_is_available(settings):
        raise ApiError(503, "The AI assistant is unavailable.", code="ai_unavailable")
    finding = get_finding_detail(session, finding_id, org_id=caller.org_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    provider = build_ai_provider(settings)
    assert provider is not None
    try:
        response = AIOrchestrator(provider).answer_question(
            context=build_finding_context(finding),
            question=payload.question,
            finding_references=finding_reference_map([finding], payload.question),
        )
        save_chat_message(
            session,
            scan_id=finding.scan_id,
            user_id=caller.sub,
            question=payload.question,
            response=response,
            scope_type="finding",
            scope_id=finding_id,
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
            "The AI assistant could not explain this finding.",
            code="ai_provider_error",
        ) from exc


@router.get(
    "/api/v1/findings/{finding_id}",
    response_model=FindingRead,
    operation_id="getFindingById",
)
def read_finding(
    finding_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> FindingRead:
    finding = get_finding_detail(session, finding_id, org_id=caller.org_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


@router.get("/api/v1/findings", response_model=FindingListResponse)
def read_findings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    severity: Severity | None = Query(None),
    scan_id: UUID | None = Query(None),
    host_id: UUID | None = None,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> FindingListResponse:
    return list_findings(
        session,
        org_id=caller.org_id,
        host_id=host_id,
        severity=severity,
        scan_id=scan_id,
        page=page,
        per_page=per_page,
    )
