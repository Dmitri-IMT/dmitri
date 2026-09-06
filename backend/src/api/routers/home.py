from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.models.persistence import utc_now
from api.schemas.home import HomeSnapshot
from api.services.home import read_home_snapshot

router = APIRouter()


@router.get("/api/v1/home", response_model=HomeSnapshot)
def read_home(
    attention_page: int = Query(1, ge=1),
    events_page: int = Query(1, ge=1),
    activity_page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> HomeSnapshot:
    return read_home_snapshot(
        session,
        org_id=caller.org_id,
        role=caller.role,
        attention_page=attention_page,
        events_page=events_page,
        activity_page=activity_page,
        now=utc_now(),
    )
