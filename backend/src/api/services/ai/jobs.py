from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.models.persistence import (
    AIScanAnalysisRecord,
    EnrichmentJobRecord,
    ScanRecord,
)
from api.schemas.ai import (
    ScanAIAnalysis,
    ScanAIAnalysisCompleted,
    ScanAIAnalysisFailed,
    ScanAIAnalysisNotRequested,
    ScanAIAnalysisQueued,
    ScanAIAnalysisResponse,
    ScanAIAnalysisUnavailable,
)
from api.services.ai.context import (
    AI_CONTEXT_VERSION,
    ScanAIContext,
    ScanAINotReadyError,
    build_scan_ai_context,
)
from api.services.ai.groq import AI_PROMPT_VERSION, AIProviderError, GroqProvider
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
        "context_version": record.context_version,
        "prompt_version": record.prompt_version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    if record.status == "completed":
        return ScanAIAnalysisCompleted(
            **fields,
            completed_at=record.completed_at,
            analysis=ScanAIAnalysis.model_validate(record.analysis_json),
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
            AIScanAnalysisRecord.scan_id == scan_id
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
    now: datetime | None = None,
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
            AIScanAnalysisRecord.scan_id == scan_id
        )
    ).first()
    current_time = now or datetime.now(timezone.utc)
    if record is not None:
        if record.status != "failed":
            raise AIAnalysisAlreadyRequestedError
        record.status = "pending"
        record.attempts = 0
        record.last_error = None
        record.next_attempt_at = None
        record.analysis_json = None
        record.context_hash = None
        record.started_at = None
        record.completed_at = None
        session.add(record)
        session.commit()
        session.refresh(record)
        return scan_ai_analysis_response(record)

    record = AIScanAnalysisRecord(
        scan_id=scan_id,
        provider=provider_name,
        model=model,
        status="pending",
        context_version=AI_CONTEXT_VERSION,
        prompt_version=AI_PROMPT_VERSION,
        created_at=current_time,
        updated_at=current_time,
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AIAnalysisAlreadyRequestedError from exc
    session.refresh(record)
    return scan_ai_analysis_response(record)


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
    def fail(code: str, retryable: bool) -> None:
        retry_or_fail(
            record,
            error=code,
            retryable=retryable,
            max_attempts=max_attempts,
            delay_seconds=retry_delay_seconds,
            now=now,
        )
        session.add(record)
        session.commit()

    scan = session.get(ScanRecord, record.scan_id)
    if scan is None or scan.org_id is None:
        return fail("scan_unavailable", False)

    try:
        context = build_scan_ai_context(
            session, scan, max_findings=max_findings
        )
        analysis = None if context is None else provider.analyze_scan(context)
    except AIProviderError as exc:
        return fail(exc.code, exc.retryable)
    except ScanAINotReadyError:
        return fail("invalid_analysis", False)
    except Exception:
        logger.exception("AI analysis job failed scan_id=%s", record.scan_id)
        return fail("internal_error", False)
    if context is None or analysis is None:
        return fail("scan_unavailable", False)
    if not _is_grounded(context, analysis):
        return fail("invalid_analysis", False)

    record.status = "completed"
    record.analysis_json = analysis.model_dump(mode="json")
    record.context_hash = _context_hash(context)
    record.completed_at = now
    session.add(record)
    session.commit()


def _is_grounded(context: ScanAIContext, analysis: ScanAIAnalysis) -> bool:
    allowed = {finding.finding_id for finding in context.top_findings}
    explained = [item.finding_id for item in analysis.important_findings]
    referenced = set(explained).union(
        *(action.related_finding_ids for action in analysis.priority_actions)
    )
    return referenced <= allowed and len(explained) == len(set(explained))


def _context_hash(context: ScanAIContext) -> str:
    canonical = json.dumps(
        context.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
