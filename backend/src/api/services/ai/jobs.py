from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.core.config import Settings, get_settings
from api.models.persistence import (
    AIScanAnalysisRecord,
    EnrichmentJobRecord,
    ScanRecord,
)
from api.schemas.ai import (
    AIProviderRecommendedAction,
    ProviderScanAIAnalysis,
    ScanAIAnalysis,
    ScanAIAnalysisCompleted,
    ScanAIAnalysisFailed,
    ScanAIAnalysisNotRequested,
    ScanAIAnalysisQueued,
    ScanAIAnalysisResponse,
    ScanAIAnalysisUnavailable,
)
from api.services.ai.analyzer import AnalysisCoverage
from api.services.ai.context import (
    AI_CONTEXT_VERSION,
    ScanAIContext,
    ScanAINotReadyError,
    build_scan_ai_context,
    materialize_scan_ai_analysis,
)
from api.services.ai.groq import (
    AI_PROMPT_VERSION,
    GROQ_PROVIDER_ID,
    AIProviderError,
    GroqProvider,
)
from api.services.ai.telemetry import drain_provider_usage, persist_usage_events
from api.services.ai.validation import (
    AIAnalysisValidationError,
    sanitize_scan_ai_analysis,
    validate_provider_analysis,
)
from api.services.ai.writing import (
    WRITING_SKILL_VERSION,
    WritingStyleViolation,
    lint_provider_analysis,
)
from api.services.jobs import claim_jobs, retry_or_fail

logger = logging.getLogger(__name__)
ACTIVE_ENRICHMENT_STATUSES = ("pending", "running")


class AIAnalysisAlreadyRequestedError(ValueError):
    pass


def scan_ai_analysis_response(
    record: AIScanAnalysisRecord,
) -> ScanAIAnalysisResponse:
    fields = {
        "scan_id": record.scan_id,
        "analysis_id": record.analysis_id,
        "status": record.status,
        "provider": record.provider,
        "model": record.model,
        "language": record.language,
        "context_version": record.context_version,
        "prompt_version": record.prompt_version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    if record.status == "completed":
        return ScanAIAnalysisCompleted(
            **fields,
            completed_at=record.completed_at,
            analysis=sanitize_scan_ai_analysis(
                ScanAIAnalysis.model_validate(record.analysis_json)
            ),
        )
    if record.status == "failed":
        return ScanAIAnalysisFailed(**fields, completed_at=record.completed_at)
    return ScanAIAnalysisQueued(**fields)


def get_scan_ai_analysis(
    session: Session,
    scan_id: UUID,
    *,
    org_id: UUID,
    ai_enabled: bool,
    language: str = "en",
) -> ScanAIAnalysisResponse | None:
    scan = session.exec(
        select(ScanRecord).where(
            ScanRecord.scan_id == scan_id,
            ScanRecord.org_id == org_id,
        )
    ).first()
    if scan is None:
        return None

    if not ai_enabled or scan.status != "completed":
        return ScanAIAnalysisUnavailable(scan_id=scan_id, status="unavailable")

    record = session.exec(
        select(AIScanAnalysisRecord).where(
            AIScanAnalysisRecord.scan_id == scan_id,
            AIScanAnalysisRecord.language == language,
        )
    ).first()
    if record is None:
        return ScanAIAnalysisNotRequested(scan_id=scan_id, status="not_requested")

    return scan_ai_analysis_response(record)


def request_scan_ai_analysis(
    session: Session,
    scan_id: UUID,
    *,
    org_id: UUID,
    ai_enabled: bool,
    provider_name: str,
    model: str,
    language: str = "en",
    now: datetime | None = None,
    commit: bool = True,
) -> ScanAIAnalysisResponse | None:
    scan = session.exec(
        select(ScanRecord).where(
            ScanRecord.scan_id == scan_id,
            ScanRecord.org_id == org_id,
        )
    ).first()
    if scan is None:
        return None
    if not ai_enabled or scan.status != "completed":
        return ScanAIAnalysisUnavailable(scan_id=scan_id, status="unavailable")

    record = session.exec(
        select(AIScanAnalysisRecord).where(
            AIScanAnalysisRecord.scan_id == scan_id,
            AIScanAnalysisRecord.language == language,
        )
    ).first()
    current_time = now or datetime.now(timezone.utc)
    if record is not None:
        if record.status != "failed":
            raise AIAnalysisAlreadyRequestedError
        record.status = "pending"
        record.attempts = 0
        record.last_error = None
        record.prompt_version = AI_PROMPT_VERSION
        record.writing_skill_version = WRITING_SKILL_VERSION
        record.next_attempt_at = None
        record.analysis_json = None
        record.context_hash = None
        record.started_at = None
        record.completed_at = None
        session.add(record)
        if commit:
            session.commit()
            session.refresh(record)
        return scan_ai_analysis_response(record)

    record = AIScanAnalysisRecord(
        scan_id=scan_id,
        provider=provider_name,
        model=model,
        language=language,
        status="pending",
        context_version=AI_CONTEXT_VERSION,
        prompt_version=AI_PROMPT_VERSION,
        writing_skill_version=WRITING_SKILL_VERSION,
        created_at=current_time,
        updated_at=current_time,
    )
    session.add(record)
    if commit:
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise AIAnalysisAlreadyRequestedError from exc
        session.refresh(record)
    return scan_ai_analysis_response(record)


def enqueue_auto_scan_analysis(
    session: Session,
    scan_id: UUID,
    *,
    settings: Settings | None = None,
    commit: bool = True,
) -> bool:
    """Create one analysis job after all enrichment jobs reach a terminal state."""
    resolved_settings = settings or get_settings()
    if not resolved_settings.ai_auto_analysis or not resolved_settings.ai_enabled:
        return False
    if (
        resolved_settings.ai_api_key is None
        or not resolved_settings.ai_api_key.get_secret_value().strip()
    ):
        return False
    active_enrichment = session.exec(
        select(EnrichmentJobRecord.id).where(
            EnrichmentJobRecord.scan_id == scan_id,
            EnrichmentJobRecord.status.in_(ACTIVE_ENRICHMENT_STATUSES),
        )
    ).first()
    if active_enrichment is not None:
        return False
    try:
        request_scan_ai_analysis(
            session,
            scan_id,
            org_id=_scan_org_id(session, scan_id),
            ai_enabled=True,
            provider_name=GROQ_PROVIDER_ID,
            model=resolved_settings.ai_model,
            language="en",
            commit=commit,
        )
    except AIAnalysisAlreadyRequestedError:
        return False
    return True


def _scan_org_id(session: Session, scan_id: UUID) -> UUID:
    scan = session.get(ScanRecord, scan_id)
    if scan is None:
        raise ValueError("scan not found")
    return scan.org_id


def process_ready_ai_analyses(
    session: Session,
    *,
    provider: GroqProvider,
    batch_size: int,
    max_findings: int,
    max_attempts: int,
    retry_delay_seconds: float,
    stale_after_seconds: float,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.now(timezone.utc)
    records = claim_ai_analyses(
        session,
        batch_size=batch_size,
        max_attempts=max_attempts,
        stale_after_seconds=stale_after_seconds,
        now=current_time,
    )
    for record in records:
        _process_claimed_analysis(
            session,
            record,
            provider=provider,
            max_findings=max_findings,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            now=current_time,
        )
    return len(records)


def claim_ai_analyses(
    session: Session,
    *,
    batch_size: int,
    max_attempts: int,
    stale_after_seconds: float,
    now: datetime,
) -> list[AIScanAnalysisRecord]:
    active_enrichment = (
        select(EnrichmentJobRecord.id)
        .where(
            EnrichmentJobRecord.scan_id == AIScanAnalysisRecord.scan_id,
            EnrichmentJobRecord.status.in_(ACTIVE_ENRICHMENT_STATUSES),
        )
        .exists()
    )
    return claim_jobs(
        session,
        AIScanAnalysisRecord,
        running_status="processing",
        exhausted_error="processing_timeout",
        batch_size=batch_size,
        max_attempts=max_attempts,
        stale_after_seconds=stale_after_seconds,
        now=now,
        where=~active_enrichment,
    )


def _process_claimed_analysis(
    session: Session,
    record: AIScanAnalysisRecord,
    *,
    provider: GroqProvider,
    max_findings: int,
    max_attempts: int,
    retry_delay_seconds: float,
    now: datetime,
) -> None:
    def fail(
        code: str,
        retryable: bool,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        failed_scan = session.get(ScanRecord, record.scan_id)
        persist_usage_events(
            session,
            drain_provider_usage(provider),
            scan_id=record.scan_id,
            org_id=failed_scan.org_id if failed_scan else None,
        )
        retry_or_fail(
            record,
            error=code,
            retryable=retryable,
            max_attempts=max_attempts,
            delay_seconds=max(retry_delay_seconds, retry_after_seconds or 0),
            now=now,
        )
        session.add(record)
        session.commit()

    scan = session.get(ScanRecord, record.scan_id)
    if scan is None or scan.org_id is None:
        return fail("scan_unavailable", False)

    phase = "context_build"
    try:
        context = build_scan_ai_context(
            session, scan, max_findings=max_findings
        )
        provider_analysis = None
        coverage = AnalysisCoverage(0, 0, 0)
        if context is not None:
            phase = "provider_analysis"
            provider_analysis = provider.analyze_scan(
                context, language=record.language
            )
            coverage = AnalysisCoverage(
                analyzed_findings=len(context.top_findings),
                failed_findings=0,
                total_findings=len(context.top_findings),
            )
            phase = "provider_validation"
            provider_analysis = _validate_analysis_with_repair(
                provider,
                context,
                provider_analysis,
                language=record.language,
            )
            phase = "writing_validation"
            try:
                lint_provider_analysis(provider_analysis)
            except WritingStyleViolation as exc:
                provider_analysis = provider.repair_analysis(
                    context, exc.codes, language=record.language
                )
                provider_analysis = _validate_repaired_analysis(
                    context, provider_analysis, language=record.language
                )
                lint_provider_analysis(provider_analysis)
        phase = "materialization"
        analysis = (
            None
            if context is None or provider_analysis is None
            else materialize_scan_ai_analysis(context, provider_analysis)
        )
    except AIProviderError as exc:
        return fail(
            exc.code,
            exc.retryable,
            retry_after_seconds=exc.retry_after_seconds,
        )
    except WritingStyleViolation as exc:
        logger.warning(
            "AI analysis rejected scan_id=%s phase=%s code=writing_style violations=%s",
            record.scan_id,
            phase,
            exc.codes,
        )
        return fail("style_violation", False)
    except ScanAINotReadyError:
        logger.warning(
            "AI analysis rejected scan_id=%s phase=%s code=scan_not_ready",
            record.scan_id,
            phase,
        )
        return fail("invalid_analysis", False)
    except ValueError as exc:
        if isinstance(exc, AIAnalysisValidationError):
            code = {
                "analysis omits a KEV finding from actions": "missing_kev_action",
                "analysis contains an unknown reference": "unknown_reference",
                "analysis contains duplicate finding references": (
                    "duplicate_finding_reference"
                ),
            }.get(str(exc), "analysis_validation")
        elif isinstance(exc, ValidationError):
            code = "invalid_provider_model"
        else:
            code = "value_error"
        logger.warning(
            "AI analysis rejected scan_id=%s phase=%s code=%s",
            record.scan_id,
            phase,
            code,
        )
        return fail("invalid_analysis", False)
    except Exception:
        logger.error(
            "AI analysis job failed scan_id=%s phase=%s code=internal_error",
            record.scan_id,
            phase,
        )
        return fail("internal_error", False)
    if context is None or analysis is None:
        return fail("scan_unavailable", False)
    if not _is_grounded(context, analysis):
        logger.warning(
            "AI analysis rejected scan_id=%s phase=grounding "
            "code=duplicate_finding_reference",
            record.scan_id,
        )
        return fail("invalid_analysis", False)

    persist_usage_events(
        session,
        drain_provider_usage(provider),
        scan_id=record.scan_id,
        org_id=scan.org_id,
    )

    record.status = "completed"
    record.analysis_json = analysis.model_dump(mode="json")
    record.analyzed_findings = coverage.analyzed_findings
    record.failed_findings = coverage.failed_findings
    record.total_findings = coverage.total_findings
    record.context_hash = _context_hash(context)
    record.completed_at = now
    session.add(record)
    session.commit()


def _is_grounded(context: ScanAIContext, analysis: ScanAIAnalysis) -> bool:
    allowed = set(context._finding_ids_by_ref.values())
    explained = [item.finding_id for item in analysis.important_findings]
    referenced = set(explained).union(
        *(action.related_finding_ids for action in analysis.priority_actions)
    )
    return referenced <= allowed and len(explained) == len(set(explained))


def _validate_analysis_with_repair(
    provider: GroqProvider,
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
    *,
    language: str,
) -> ProviderScanAIAnalysis:
    try:
        return _validate_grounded_provider_analysis(context, analysis)
    except AIAnalysisValidationError as exc:
        repaired = provider.repair_analysis(
            context, (str(exc),), language=language
        )
        return _validate_repaired_analysis(context, repaired, language=language)


def _validate_repaired_analysis(
    context: ScanAIContext,
    repaired: ProviderScanAIAnalysis,
    *,
    language: str,
) -> ProviderScanAIAnalysis:
    try:
        return _validate_grounded_provider_analysis(context, repaired)
    except AIAnalysisValidationError as exc:
        if str(exc) != "analysis omits a KEV finding from actions":
            raise

    covered = {
        reference
        for action in repaired.priority_actions
        for reference in action.related_finding_refs
    }
    fallback_text = {
        "en": (
            "Review KEV vulnerability",
            "Apply the available vendor fix and reduce exposure while it is reviewed.",
        ),
        "pt-BR": (
            "Revisar vulnerabilidade no KEV",
            "Aplicar a corre\u00e7\u00e3o dispon\u00edvel e reduzir a "
            "exposi\u00e7\u00e3o enquanto ela \u00e9 revisada.",
        ),
        "ru": (
            "Проверить уязвимость KEV",
            "Применить доступное исправление и уменьшить открытость до завершения "
            "проверки.",
        ),
    }.get(
        language, ("Review KEV vulnerability", "Apply the available vendor fix.")
    )
    uncovered = [
        finding.finding_ref
        for finding in context.top_findings
        if finding.is_kev and finding.finding_ref not in covered
    ]
    actions = list(repaired.priority_actions)
    if len(actions) >= 15:
        kev_refs = {
            finding.finding_ref
            for finding in context.top_findings
            if finding.is_kev
        }
        counts: dict[str, int] = {}
        for action in actions:
            for reference in set(action.related_finding_refs) & kev_refs:
                counts[reference] = counts.get(reference, 0) + 1
        for index in range(len(actions) - 1, -1, -1):
            sole = any(
                counts[reference] == 1
                for reference in set(actions[index].related_finding_refs)
                & kev_refs
            )
            if not sole:
                del actions[index]
                break
    actions.append(
        AIProviderRecommendedAction(
            priority="immediate",
            title=fallback_text[0],
            description=fallback_text[1],
            related_finding_refs=uncovered,
        )
    )
    return _validate_grounded_provider_analysis(
        context, repaired.model_copy(update={"priority_actions": actions})
    )


def _validate_grounded_provider_analysis(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
) -> ProviderScanAIAnalysis:
    normalized = validate_provider_analysis(context, analysis)
    try:
        materialized = materialize_scan_ai_analysis(context, normalized)
    except ValueError as exc:
        raise AIAnalysisValidationError(
            "analysis contains an unknown reference"
        ) from exc
    if not _is_grounded(context, materialized):
        raise AIAnalysisValidationError(
            "analysis contains duplicate finding references"
        )
    return normalized


def _context_hash(context: ScanAIContext) -> str:
    canonical = json.dumps(
        context.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
