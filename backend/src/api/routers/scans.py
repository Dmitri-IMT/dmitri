from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.schemas.read import (
    ScanDetailResponse,
    ScanListResponse,
    ScanSortBy,
    ScanStatus,
    SortOrder,
)
from api.services.read import get_scan_detail, list_scans

router = APIRouter()


@router.get("/api/v1/scans", response_model=ScanListResponse)
def read_scans(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: ScanStatus | None = Query(None),
    sort_by: ScanSortBy = Query("timestamp"),
    sort_order: SortOrder = Query("desc"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> ScanListResponse:
    return list_scans(
        session,
        org_id=caller.org_id,
        page=page,
        per_page=per_page,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/api/v1/scans/{scan_id}", response_model=ScanDetailResponse)
def read_scan(
    scan_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> ScanDetailResponse:
    scan = get_scan_detail(session, scan_id, org_id=caller.org_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan
