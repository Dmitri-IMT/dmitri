from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlmodel import Session, select

from api.core.config import Settings, get_settings
from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.errors import ApiError
from api.models.persistence import AIUsageRecord
from api.schemas.ai import (
    AIChatHistoryResponse,
    AIChatResponse,
    AIContextChatRequest,
    AIUsageEntry,
    AIUsageResponse,
    AIUsageSummary,
)
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
from api.services.ai.telemetry import drain_provider_usage, persist_usage_events
from api.services.read import (
    get_finding_detail,
    get_host_detail,
    get_scan_detail,
    get_scan_risk_summary,
    list_findings,
)

router = APIRouter()


@router.get(
    "/api/v1/ai/usage",
    response_model=AIUsageResponse,
    operation_id="getAIUsage",
)
def get_ai_usage(
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> AIUsageResponse:
    """Return provider usage metadata scoped to the authenticated organization."""

    records = list(
        session.exec(
            select(AIUsageRecord)
            .where(AIUsageRecord.org_id == caller.org_id)
            .order_by(AIUsageRecord.created_at.desc())
            .limit(limit)
        ).all()
    )
    summary_row = session.exec(
        select(
            func.count(AIUsageRecord.id),
            func.coalesce(func.sum(AIUsageRecord.input_tokens), 0),
            func.coalesce(func.sum(AIUsageRecord.output_tokens), 0),
            func.coalesce(func.sum(AIUsageRecord.total_tokens), 0),
            func.coalesce(
                func.sum(case((AIUsageRecord.status != "success", 1), else_=0)), 0
            ),
        ).where(AIUsageRecord.org_id == caller.org_id)
    ).one()
    requests, input_tokens, output_tokens, total_tokens, errors = summary_row
    summary = AIUsageSummary(
        requests=int(requests or 0),
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        total_tokens=int(total_tokens or 0),
        errors=int(errors or 0),
    )
    return AIUsageResponse(
        summary=summary,
        data=[
            AIUsageEntry(
                operation=item.operation,
                provider=item.provider,
                model=item.model,
                status=item.status,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                total_tokens=item.total_tokens,
                latency_ms=item.latency_ms,
                http_status=item.http_status,
                request_id=item.request_id,
                error_code=item.error_code,
                scan_id=item.scan_id,
                created_at=item.created_at,
            )
            for item in records
        ],
    )


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
            language=payload.language,
            finding_references=finding_reference_map(findings, payload.question),
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
            scope_type=payload.scope,
            scope_id=payload.context_id,
        )
        return response
    except AIProviderError as exc:
        persist_usage_events(
            session,
            drain_provider_usage(provider),
            scan_id=scan_id,
            org_id=caller.org_id,
            user_id=caller.sub,
        )
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
