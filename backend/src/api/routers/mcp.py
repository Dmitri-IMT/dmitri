from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select

from api.core.config import get_settings
from api.db.session import get_session
from api.dependencies.auth import require_user_row
from api.models.identity import Org, User
from api.models.mcp import McpClient, McpConnection
from api.models.persistence import utc_now
from api.schemas.mcp import (
    McpAuthorizationView,
    McpConnectionList,
    McpConnectionView,
    McpConsentRequest,
    McpConsentResponse,
    McpErrorResponse,
    McpInfo,
)
from api.services import mcp_auth

router = APIRouter(
    prefix="/api/v1/mcp", tags=["MCP"],
    responses={status: {"model": McpErrorResponse} for status in (401, 404, 409, 422)},
)


def require_mcp() -> None:
    if not get_settings().mcp_public_url:
        raise HTTPException(404, "MCP is not configured")


@router.get("/info", response_model=McpInfo)
def read_mcp_info(user: User = Depends(require_user_row)) -> McpInfo:
    url = get_settings().mcp_public_url
    return McpInfo(enabled=bool(url), url=url or None)


@router.get(
    "/authorization", response_model=McpAuthorizationView,
    dependencies=[Depends(require_mcp)],
)
def read_mcp_authorization(
    response: Response,
    request_token: str = Query(
        min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    user: User = Depends(require_user_row),
    session: Session = Depends(get_session),
) -> McpAuthorizationView:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    row = mcp_auth.pending_authorization(session, request_token)
    if row is None:
        raise HTTPException(404, "Authorization request is no longer available")
    client = session.get(McpClient, row.client_id)
    org = session.get(Org, user.org_id)
    return McpAuthorizationView(
        client_name=client.metadata_json.get("client_name") or "Local MCP client",
        redirect_uri=row.params_json["redirect_uri"], organization=org.name,
        email=user.email,
    )


@router.post(
    "/authorization", response_model=McpConsentResponse,
    dependencies=[Depends(require_mcp)],
)
def decide_mcp_authorization(
    body: McpConsentRequest,
    response: Response,
    user: User = Depends(require_user_row),
    session: Session = Depends(get_session),
) -> McpConsentResponse:
    response.headers["Cache-Control"] = "no-store"
    url = mcp_auth.consent(session, body.request_token, user, body.approve)
    if url is None:
        raise HTTPException(
            409, "Request expired, was used, or connection limit reached"
        )
    return McpConsentResponse(redirect_url=url)


@router.get(
    "/connections", response_model=McpConnectionList,
    dependencies=[Depends(require_mcp)],
)
def read_mcp_connections(
    user: User = Depends(require_user_row),
    session: Session = Depends(get_session),
) -> McpConnectionList:
    rows = session.exec(select(McpConnection, McpClient).join(
        McpClient, McpClient.id == McpConnection.client_id,
    ).where(
        McpConnection.user_id == user.id, McpConnection.org_id == user.org_id,
        McpConnection.revoked_at.is_(None), McpConnection.expires_at > utc_now(),
    ).order_by(McpConnection.created_at.desc()).limit(50)).all()
    return McpConnectionList(data=[McpConnectionView(
        id=connection.id,
        client_name=client.metadata_json.get("client_name") or "Local MCP client",
        created_at=connection.created_at, expires_at=connection.expires_at,
        last_used_at=connection.last_used_at,
    ) for connection, client in rows])


@router.delete(
    "/connections/{connection_id}", status_code=204,
    dependencies=[Depends(require_mcp)],
)
def disconnect_mcp(
    connection_id: UUID,
    user: User = Depends(require_user_row),
    session: Session = Depends(get_session),
) -> None:
    row = session.exec(select(McpConnection).where(
        McpConnection.id == connection_id, McpConnection.user_id == user.id,
        McpConnection.org_id == user.org_id,
    ).with_for_update()).first()
    if row is None:
        raise HTTPException(404, "Connection not found")
    row.revoked_at = row.revoked_at or utc_now()
    session.add(row)
    session.commit()
