from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_admin, require_user
from api.errors import ApiError
from api.models.persistence import utc_now
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


@router.post(
    "/api/v1/commands/{command_id}/cancel",
    response_model=CommandDetail,
    operation_id="cancelCommand",
    responses={
        202: {
            "model": CommandDetail,
            "description": "The cancel frame was sent to the connected agent.",
        },
        409: {"description": "The command is already uploading scan results."},
    },
)
async def cancel_command_route(
    command_id: UUID,
    response: Response,
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_admin),
) -> CommandDetail:
    try:
        result = await commands.cancel_command(
            session,
            org_id=caller.org_id,
            command_id=command_id,
            now=utc_now(),
        )
    except commands.CommandNotCancellableError as exc:
        raise ApiError(
            409,
            "The scan is already uploading its results.",
            code="command_not_cancellable",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Command not found")
    detail, status_code = result
    response.status_code = status_code
    return detail


@router.options("/api/v1/commands/{command_id}", status_code=204)
def options_command() -> None:
    return None
