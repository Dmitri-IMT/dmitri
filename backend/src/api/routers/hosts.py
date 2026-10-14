from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_admin_row, require_user
from api.models.identity import User
from api.schemas.deletion import HostDeletionResponse
from api.schemas.read import (
    HostDetailResponse,
    HostGroup,
    HostListResponse,
    HostSortBy,
    SortOrder,
)
from api.services.deletion import delete_all_hosts, delete_host
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
    group: HostGroup = Query("active"),
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
        group=group,
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


@router.delete(
    "/api/v1/hosts",
    response_model=HostDeletionResponse,
    operation_id="deleteAllHosts",
)
def delete_all_hosts_route(
    actor: User = Depends(require_admin_row),
    session: Session = Depends(get_session),
) -> HostDeletionResponse:
    return HostDeletionResponse(
        deleted=delete_all_hosts(session, org_id=actor.org_id, actor=actor)
    )


@router.delete(
    "/api/v1/hosts/{host_id}", status_code=204, operation_id="deleteHost"
)
def delete_host_route(
    host_id: UUID,
    actor: User = Depends(require_admin_row),
    session: Session = Depends(get_session),
) -> None:
    if not delete_host(session, host_id=host_id, org_id=actor.org_id, actor=actor):
        raise HTTPException(status_code=404, detail="Host not found")
