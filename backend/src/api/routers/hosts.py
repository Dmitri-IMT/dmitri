from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.schemas.read import HostDetailResponse, HostListResponse
from api.services.read import get_host_detail, list_hosts

router = APIRouter()


@router.get("/api/v1/hosts", response_model=HostListResponse)
def read_hosts(
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> HostListResponse:
    return list_hosts(session, org_id=caller.org_id)


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
