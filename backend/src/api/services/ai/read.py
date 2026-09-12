from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from api.models.persistence import AIScanAnalysisRecord, ScanRecord
from api.schemas.ai import AIAnalysisReadStatus, ScanAIAnalysisResponse
from api.services.ai.schemas import ScanAIAnalysis


def _empty_analysis_response(
    scan_id: UUID,
    status: AIAnalysisReadStatus,
) -> ScanAIAnalysisResponse:
    return ScanAIAnalysisResponse(
        scan_id=scan_id,
        analysis_id=None,
        status=status,
        analysis=None,
        provider=None,
        model=None,
        context_version=None,
        prompt_version=None,
        created_at=None,
        updated_at=None,
        completed_at=None,
    )


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

    if not ai_enabled or scan.status == "failed":
        return _empty_analysis_response(scan_id, "unavailable")

    record = session.exec(
        select(AIScanAnalysisRecord).where(
            AIScanAnalysisRecord.scan_id == scan_id
        )
    ).first()
    if record is None:
        return _empty_analysis_response(scan_id, "pending")

    analysis = (
        ScanAIAnalysis.model_validate(record.analysis_json)
        if record.status == "completed" and record.analysis_json is not None
        else None
    )
    return ScanAIAnalysisResponse(
        scan_id=scan_id,
        analysis_id=record.analysis_id,
        status=record.status,
        analysis=analysis,
        provider=record.provider,
        model=record.model,
        context_version=record.context_version,
        prompt_version=record.prompt_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )
