from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from api.models.persistence import (
    AIScanAnalysisRecord,
    EnrichmentJobRecord,
    ScanRecord,
)
from api.services.ai.analyzer import generate_scan_analysis
from api.services.ai.context import ScanAINotReadyError, build_scan_ai_context
from api.services.ai.prompts import AI_PROMPT_VERSION
from api.services.ai.provider import AIProvider, AIProviderError
from api.services.ai.schemas import AI_CONTEXT_VERSION, ScanAIContext
from api.services.ai.validation import AIAnalysisValidationError

logger = logging.getLogger(__name__)
ACTIVE_ENRICHMENT_STATUSES = ("pending", "running")


def process_ready_ai_analyses(
    session: Session,
    *,
    provider: AIProvider,
    provider_name: str,
    model: str,
    batch_size: int,
    max_findings: int,
    max_attempts: int,
    retry_delay_seconds: float,
    stale_after_seconds: float,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.now(timezone.utc)
    enqueue_ready_ai_analyses(
        session,
        provider_name=provider_name,
        model=model,
        batch_size=batch_size,
    )
    records = claim_ai_analyses(
        session,
        batch_size=batch_size,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
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
            now=current_time,
        )
    return len(records)


def enqueue_ready_ai_analyses(
    session: Session,
    *,
    provider_name: str,
    model: str,
    batch_size: int,
) -> int:
    active_enrichment = (
        select(EnrichmentJobRecord.id)
        .where(
            EnrichmentJobRecord.scan_id == ScanRecord.scan_id,
            EnrichmentJobRecord.status.in_(ACTIVE_ENRICHMENT_STATUSES),
        )
        .exists()
    )
    existing_analysis = (
        select(AIScanAnalysisRecord.id)
        .where(AIScanAnalysisRecord.scan_id == ScanRecord.scan_id)
        .exists()
    )
    statement = (
        select(ScanRecord)
        .where(
            ScanRecord.status == "completed",
            ScanRecord.org_id.is_not(None),
            ~active_enrichment,
            ~existing_analysis,
        )
        .order_by(ScanRecord.created_at, ScanRecord.scan_id)
        .limit(batch_size)
    )
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    scans = session.exec(statement).all()
    for scan in scans:
        session.add(
            AIScanAnalysisRecord(
                scan_id=scan.scan_id,
                provider=provider_name,
                model=model,
                status="pending",
                context_version=AI_CONTEXT_VERSION,
                prompt_version=AI_PROMPT_VERSION,
            )
        )
    session.commit()
    return len(scans)


def claim_ai_analyses(
    session: Session,
    *,
    batch_size: int,
    max_attempts: int,
    retry_delay_seconds: float,
    stale_after_seconds: float,
    now: datetime,
) -> list[AIScanAnalysisRecord]:
    retry_before = now - timedelta(seconds=retry_delay_seconds)
    stale_before = now - timedelta(seconds=stale_after_seconds)

    exhausted = session.exec(
        select(AIScanAnalysisRecord).where(
            AIScanAnalysisRecord.status == "processing",
            AIScanAnalysisRecord.started_at <= stale_before,
            AIScanAnalysisRecord.attempts >= max_attempts,
        )
    ).all()
    for record in exhausted:
        record.status = "failed"
        record.last_error_code = "processing_timeout"
        record.completed_at = now
        record.updated_at = now
        session.add(record)
    if exhausted:
        session.commit()

    eligible_pending = (
        (AIScanAnalysisRecord.status == "pending")
        & (AIScanAnalysisRecord.attempts < max_attempts)
        & or_(
            AIScanAnalysisRecord.started_at.is_(None),
            AIScanAnalysisRecord.started_at <= retry_before,
        )
    )
    eligible_stale = (
        (AIScanAnalysisRecord.status == "processing")
        & (AIScanAnalysisRecord.attempts < max_attempts)
        & (AIScanAnalysisRecord.started_at <= stale_before)
    )
    statement = (
        select(AIScanAnalysisRecord)
        .where(or_(eligible_pending, eligible_stale))
        .order_by(AIScanAnalysisRecord.created_at, AIScanAnalysisRecord.id)
        .limit(batch_size)
    )
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    records = session.exec(statement).all()
    for record in records:
        record.status = "processing"
        record.attempts += 1
        record.started_at = now
        record.completed_at = None
        record.updated_at = now
        session.add(record)
    session.commit()
    for record in records:
        session.refresh(record)
    return records


def _process_claimed_analysis(
    session: Session,
    record: AIScanAnalysisRecord,
    *,
    provider: AIProvider,
    max_findings: int,
    max_attempts: int,
    now: datetime,
) -> None:
    scan = session.get(ScanRecord, record.scan_id)
    if scan is None or scan.org_id is None:
        _fail_record(session, record, "scan_unavailable", now=now)
        return

    try:
        context = build_scan_ai_context(
            session,
            scan.scan_id,
            org_id=scan.org_id,
            max_findings=max_findings,
        )
        if context is None:
            _fail_record(session, record, "scan_unavailable", now=now)
            return
        analysis = generate_scan_analysis(provider, context)
    except AIProviderError as exc:
        _handle_attempt_error(
            session,
            record,
            code=exc.code,
            retryable=exc.retryable,
            max_attempts=max_attempts,
            now=now,
        )
        return
    except (AIAnalysisValidationError, ScanAINotReadyError):
        _handle_attempt_error(
            session,
            record,
            code="invalid_analysis",
            retryable=False,
            max_attempts=max_attempts,
            now=now,
        )
        return
    except Exception:
        logger.exception("AI analysis job failed scan_id=%s", record.scan_id)
        _handle_attempt_error(
            session,
            record,
            code="internal_error",
            retryable=False,
            max_attempts=max_attempts,
            now=now,
        )
        return

    record.status = "completed"
    record.analysis_json = analysis.model_dump(mode="json")
    record.context_hash = _context_hash(context)
    record.last_error_code = None
    record.completed_at = now
    record.updated_at = now
    session.add(record)
    session.commit()


def _handle_attempt_error(
    session: Session,
    record: AIScanAnalysisRecord,
    *,
    code: str,
    retryable: bool,
    max_attempts: int,
    now: datetime,
) -> None:
    if retryable and record.attempts < max_attempts:
        record.status = "pending"
        record.completed_at = None
    else:
        record.status = "failed"
        record.completed_at = now
    record.last_error_code = code
    record.updated_at = now
    session.add(record)
    session.commit()


def _fail_record(
    session: Session,
    record: AIScanAnalysisRecord,
    code: str,
    *,
    now: datetime,
) -> None:
    record.status = "failed"
    record.last_error_code = code
    record.completed_at = now
    record.updated_at = now
    session.add(record)
    session.commit()


def _context_hash(context: ScanAIContext) -> str:
    canonical = json.dumps(
        context.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
