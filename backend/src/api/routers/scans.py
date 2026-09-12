from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity, require_agent
from api.dependencies.auth import CallerIdentity, require_user
from api.models.persistence import utc_now
from api.schemas.read import (
    ScanDetailResponse,
    ScanListResponse,
    ScanSortBy,
    ScanStatus,
    SortOrder,
)
from api.schemas.scan import ScanIngestAcceptedResponse, ScanIngestRequest
from api.services.persistence import ScanClosedError, ScanOwnershipError, ingest_scan
from api.services.read import get_scan_detail, list_scans

router = APIRouter()


@router.post(
    "/api/v1/scans",
    response_model=ScanIngestAcceptedResponse,
    status_code=202,
    operation_id="ingestScan",
)
def ingest_scan_route(
    payload: ScanIngestRequest,
    identity: AgentIdentity = Depends(require_agent),
    session: Session = Depends(get_session),
) -> ScanIngestAcceptedResponse:
    try:
        ingest_scan(session, payload, identity=identity, now=utc_now())
    except ScanOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except ScanClosedError as exc:
        raise HTTPException(
            status_code=400, detail="Scan is no longer accepting results"
        ) from exc

    return ScanIngestAcceptedResponse(
        message="scan received successfully",
        scan_id=payload.scan_id,
        hosts_received=len(payload.hosts),
        status="accepted",
    )


@router.get("/api/v1/scans", response_model=ScanListResponse)
def read_scans(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: ScanStatus | None = Query(None),
    agent_id: UUID | None = Query(None),
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
        agent_id=agent_id,
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
