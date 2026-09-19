from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.core.config import Settings, get_settings
from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.errors import ApiError
from api.schemas.ai import AIChatHistoryResponse, AIChatResponse, AIContextChatRequest
from api.services.ai.chat import (
    build_chat_context,
    build_finding_context,
    build_host_context,
    finding_reference_map,
    list_chat_messages,
    save_chat_message,
)
from api.services.ai.groq import AIProviderError, ai_is_available, build_ai_provider
from api.services.ai.jobs import get_scan_ai_analysis
from api.services.ai.orchestrator import AIOrchestrator
from api.services.read import (
    get_finding_detail,
    get_host_detail,
    get_scan_detail,
    get_scan_risk_summary,
    list_findings,
)

router = APIRouter()


@router.get(
    "/api/v1/ai/chat/history",
    response_model=AIChatHistoryResponse,
    operation_id="listContextAIChat",
)
def list_context_chat(
    scope: str = Query(..., pattern="^(scan|host|finding)$"),
    context_id: UUID = Query(...),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> AIChatHistoryResponse:
    scan_id = _resolve_scan_id(session, scope, context_id, caller.org_id)
    if scan_id is None:
        raise HTTPException(status_code=404, detail="Context not found")
    return AIChatHistoryResponse(
        data=list_chat_messages(
            session,
            scan_id=scan_id,
            org_id=caller.org_id,
            scope_type=scope,
            scope_id=context_id,
        )
    )


@router.post(
    "/api/v1/ai/chat",
    response_model=AIChatResponse,
    operation_id="askContextAI",
)
def ask_context_chat(
    payload: AIContextChatRequest,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AIChatResponse:
    if not ai_is_available(settings):
        raise ApiError(503, "The AI assistant is unavailable.", code="ai_unavailable")
    resolved = _build_context(session, payload.scope, payload.context_id, caller.org_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Context not found")
    context, scan_id, findings = resolved
    provider = build_ai_provider(settings)
    assert provider is not None
    try:
        response = AIOrchestrator(provider).answer_question(
            context=context,
            question=payload.question,
            finding_references=finding_reference_map(findings, payload.question),
        )
        save_chat_message(
            session,
            scan_id=scan_id,
            user_id=caller.sub,
            question=payload.question,
            response=response,
            scope_type=payload.scope,
            scope_id=payload.context_id,
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
        if exc.code == "provider_context_too_large":
            raise ApiError(
                413,
                "O contexto é grande demais. Tente uma pergunta mais específica.",
                code="ai_context_too_large",
            ) from exc
        raise ApiError(
            502,
            "The AI assistant could not answer this question.",
            code="ai_provider_error",
        ) from exc


def _resolve_scan_id(
    session: Session, scope: str, context_id: UUID, org_id: UUID
) -> UUID | None:
    resolved = _build_context(session, scope, context_id, org_id)
    return resolved[1] if resolved else None


def _build_context(
    session: Session, scope: str, context_id: UUID, org_id: UUID
) -> tuple[dict[str, object], UUID, list[object]] | None:
    if scope == "scan":
        detail = get_scan_detail(session, context_id, org_id=org_id)
        if detail is None or detail.status != "completed":
            return None
        risk = get_scan_risk_summary(session, context_id, org_id=org_id)
        if risk is None:
            return None
        analysis = get_scan_ai_analysis(
            session, context_id, org_id=org_id, ai_enabled=True
        )
        findings = list(detail.findings)
        return build_chat_context(detail, risk, analysis), context_id, findings
    if scope == "host":
        host = get_host_detail(session, context_id, org_id=org_id)
        if host is None or not host.scan_history:
            return None
        findings = list_findings(
            session, org_id=org_id, host_id=context_id, per_page=100
        ).data
        return (
            build_host_context(host, findings),
            host.scan_history[0].scan_id,
            findings,
        )
    finding = get_finding_detail(session, context_id, org_id=org_id)
    if finding is None:
        return None
    return build_finding_context(finding), finding.scan_id, [finding]
