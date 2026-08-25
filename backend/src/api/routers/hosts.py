from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.schemas.read import (
    HostDetailResponse,
    HostListResponse,
    HostSortBy,
    SortOrder,
)
from api.services.read import (
    DEFAULT_PAGE,
    DEFAULT_PER_PAGE,
    get_host_detail,
    list_hosts,
)

router = APIRouter()


@router.get("/api/v1/hosts", response_model=HostListResponse)
def read_hosts(
    page: int = Query(DEFAULT_PAGE, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=100),
    sort_by: HostSortBy = Query("last_seen_at"),
    sort_order: SortOrder = Query("desc"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> HostListResponse:
    return list_hosts(
        session,
        org_id=caller.org_id,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/api/v1/hosts/{host_id}", response_model=HostDetailResponse)
def read_host(
    host_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> HostDetailResponse:
    host = get_host_detail(session, host_id, org_id=caller.org_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    return host
