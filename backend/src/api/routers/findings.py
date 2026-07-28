from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.schemas.read import FindingListResponse, Severity
from api.services.read import list_findings

router = APIRouter()


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
