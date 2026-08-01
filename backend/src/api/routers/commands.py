from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_user
from api.schemas.commands import CommandDetail
from api.services import commands

router = APIRouter()


@router.get("/api/v1/commands/{command_id}", response_model=CommandDetail)
def read_command(
    command_id: UUID,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> CommandDetail:
    detail = commands.get_command_detail(session, command_id, org_id=caller.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return detail


@router.options("/api/v1/commands/{command_id}", status_code=204)
def options_command() -> None:
    return None
