from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from api.core.config import Settings, get_settings
from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.errors import ApiError
from api.models.persistence import AIExplanationRecord, AIUsageRecord
from api.schemas.ai import (
    AIChatHistoryResponse,
    AIChatResponse,
    AIContextChatRequest,
    AIExplainRequest,
    AIExplanationResponse,
    AIUsageEntry,
    AIUsageResponse,
    AIUsageSummary,
    MachineExplanationResponse,
    ScanExplanationResponse,
)
from api.services.ai.chat import (
    AIChatContextBundle,
    answer_interactive_question,
    build_finding_chat_bundle,
    build_host_chat_bundle,
    build_scan_chat_bundle,
    context_findings,
    list_chat_messages,
    save_chat_message,
    scrub_secrets,
)
from api.services.ai.chat_errors import chat_api_error_message
from api.services.ai.context import describe_observed_products
from api.services.ai.explanations import explanation_context, materialize_explanation
from api.services.ai.openai_responses import (
    AI_PROMPT_VERSION,
    AIProviderError,
    ai_is_available,
    build_ai_provider,
)
from api.services.ai.research import attach_cached_fix_records
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
    now = datetime.now(timezone.utc)
    asked_today = session.exec(
        select(func.count(AIUsageRecord.id)).where(
            AIUsageRecord.user_id == caller.sub,
            AIUsageRecord.operation.in_(("chat", "explain_scan", "explain_host")),
            AIUsageRecord.created_at >= now - timedelta(days=1),
        )
    ).one()
    if asked_today >= settings.ai_chat_daily_limit:
        raise ApiError(
            429,
            chat_api_error_message(
                "ai_daily_limit",
                language=payload.language,
                limit=settings.ai_chat_daily_limit,
            ),
            code="ai_daily_limit",
        )
    resolved = _build_context(
        session,
        payload.scope,
        payload.context_id,
        caller.org_id,
        question=payload.question,
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail="Context not found")
    bundle, scan_id = resolved
    findings = context_findings(bundle.provider_context)
    describe_observed_products(session, findings, bundle.finding_ids_by_ref)
    attach_cached_fix_records(session, findings, now=now)
    provider = build_ai_provider(settings)
    assert provider is not None
    try:
        response = answer_interactive_question(
            provider,
            bundle,
            question=payload.question,
            language=payload.language,
        )
        persist_usage_events(
            session,
            drain_provider_usage(provider),
            scan_id=scan_id,
            org_id=caller.org_id,
            user_id=caller.sub,
            commit=False,
        )
        save_chat_message(
            session,
            scan_id=scan_id,
            user_id=caller.sub,
            question=scrub_secrets(payload.question),
            response=response,
            scope_type=payload.scope,
            scope_id=payload.context_id,
            commit=False,
        )
        session.commit()
        return response
    except AIProviderError as exc:
        # The tokens were spent even though the answer failed, so the usage rows
        # are committed on their own. There is no transcript to pair them with.
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
                chat_api_error_message(
                    "ai_rate_limited",
                    language=payload.language,
                    seconds=wait_seconds,
                ),
                code="ai_rate_limited",
            ) from exc
        if exc.code == "provider_context_too_large":
            raise ApiError(
                413,
                chat_api_error_message(
                    "ai_context_too_large", language=payload.language
                ),
                code="ai_context_too_large",
            ) from exc
        raise ApiError(
            502,
            "The AI assistant could not answer this question.",
            code="ai_provider_error",
        ) from exc


@router.post(
    "/api/v1/ai/explain",
    response_model=AIExplanationResponse,
    operation_id="explainAIContext",
)
def explain_context(
    payload: AIExplainRequest,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AIExplanationResponse:
    resolved = explanation_context(
        session, payload.scope, payload.context_id, caller.org_id, payload.language
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail="Context not found")
    bundle, scan_id, leads = resolved
    cached = session.exec(
        select(AIExplanationRecord).where(
            AIExplanationRecord.scope == payload.scope,
            AIExplanationRecord.context_id == payload.context_id,
            AIExplanationRecord.language == payload.language,
            AIExplanationRecord.prompt_version == AI_PROMPT_VERSION,
        )
    ).first()
    response_type = (
        ScanExplanationResponse if payload.scope == "scan"
        else MachineExplanationResponse
    )
    if cached is not None and cached.scan_id == scan_id:
        return response_type(
            scope=payload.scope, context_id=payload.context_id,
            language=payload.language, created_at=cached.created_at,
            explanation=cached.explanation_json,
        )
    if not ai_is_available(settings):
        raise ApiError(503, "The AI assistant is unavailable.", code="ai_unavailable")
    now = datetime.now(timezone.utc)
    asked_today = session.exec(
        select(func.count(AIUsageRecord.id)).where(
            AIUsageRecord.user_id == caller.sub,
            AIUsageRecord.operation.in_(("chat", "explain_scan", "explain_host")),
            AIUsageRecord.created_at >= now - timedelta(days=1),
        )
    ).one()
    if asked_today >= settings.ai_chat_daily_limit:
        raise ApiError(
            429,
            chat_api_error_message(
                "ai_daily_limit", language=payload.language,
                limit=settings.ai_chat_daily_limit,
            ),
            code="ai_daily_limit",
        )
    provider = build_ai_provider(settings)
    assert provider is not None
    try:
        result = provider.explain_context(
            {"facts": bundle.provider_context.model_dump(mode="json"),
             "allowed_leads": leads},
            scope=payload.scope, language=payload.language,
        )
        explanation = materialize_explanation(result, bundle, leads)
    except AIProviderError as exc:
        persist_usage_events(
            session, drain_provider_usage(provider), scan_id=scan_id,
            org_id=caller.org_id, user_id=caller.sub,
        )
        code = (
            "ai_rate_limited" if exc.code == "provider_rate_limited"
            else "ai_provider_error"
        )
        raise ApiError(
            429 if code == "ai_rate_limited" else 502,
            "Dmitri could not explain this context right now.", code=code,
        ) from exc
    persist_usage_events(
        session, drain_provider_usage(provider), scan_id=scan_id,
        org_id=caller.org_id, user_id=caller.sub, commit=False,
    )
    values = dict(
        scope=payload.scope, context_id=payload.context_id,
        scan_id=scan_id, language=payload.language,
        prompt_version=AI_PROMPT_VERSION,
        explanation_json=explanation.model_dump(mode="json"), created_at=now,
    )
    session.execute(
        insert(AIExplanationRecord).values(**values).on_conflict_do_update(
            constraint="uq_ai_explanations_context",
            set_={
                key: values[key]
                for key in ("scan_id", "explanation_json", "created_at")
            },
        )
    )
    session.commit()
    return response_type(
        scope=payload.scope, context_id=payload.context_id,
        language=payload.language, created_at=now, explanation=explanation,
    )


def _resolve_scan_id(
    session: Session, scope: str, context_id: UUID, org_id: UUID
) -> UUID | None:
    """Check the context exists and name its scan, without building a prompt."""
    if scope == "scan":
        detail = get_scan_detail(session, context_id, org_id=org_id)
        return context_id if detail is not None else None
    if scope == "host":
        host = get_host_detail(session, context_id, org_id=org_id)
        if host is None or not host.scan_history:
            return None
        return host.scan_history[0].scan_id
    finding = get_finding_detail(session, context_id, org_id=org_id)
    return finding.scan_id if finding is not None else None


def _build_context(
    session: Session,
    scope: str,
    context_id: UUID,
    org_id: UUID,
    *,
    question: str,
) -> tuple[AIChatContextBundle, UUID] | None:
    if scope == "scan":
        detail = get_scan_detail(session, context_id, org_id=org_id)
        if detail is None or detail.status != "completed":
            return None
        risk = get_scan_risk_summary(session, context_id, org_id=org_id)
        if risk is None:
            return None
        return build_scan_chat_bundle(detail, risk, question), context_id
    if scope == "host":
        host = get_host_detail(session, context_id, org_id=org_id)
        if host is None or not host.scan_history:
            return None
        finding_result = list_findings(
            session, org_id=org_id, host_id=context_id, per_page=100
        )
        return build_host_chat_bundle(
            host, finding_result.data, finding_result.evidence_summary
        ), host.scan_history[0].scan_id
    finding = get_finding_detail(session, context_id, org_id=org_id)
    if finding is None:
        return None
    return build_finding_chat_bundle(finding), finding.scan_id
