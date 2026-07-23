from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import Session

from api.db.session import get_session
from api.schemas.read import FindingListResponse
from api.services.read import list_findings

router = APIRouter()


@router.get("/api/v1/findings", response_model=FindingListResponse)
def read_findings(
    host_id: UUID | None = None,
    session: Session = Depends(get_session),
) -> FindingListResponse:
    return list_findings(session, host_id=host_id)
