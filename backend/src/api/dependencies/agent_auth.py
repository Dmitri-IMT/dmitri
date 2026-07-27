from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, Request, WebSocket
from pydantic import BaseModel
from sqlmodel import Session

from api.core.config import get_settings
from api.db.session import get_session
from api.models.command import Agent
from api.models.persistence import utc_now
from api.services import device_sig
from api.services.nonces import NonceReplayError, prune_expired_nonces, remember_nonce


class AgentIdentity(BaseModel):
    agent_id: UUID
    org_id: UUID


class AgentAuthError(Exception):
    pass


class AgentUnauthenticated(AgentAuthError):
    pass


class AgentRevoked(AgentAuthError):
    pass


def authenticate_agent(
    session: Session,
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    now: datetime,
    expected_agent_id: UUID | None = None,
) -> AgentIdentity:
    """remember_nonce commits internally, so a request whose signature verifies durably
    burns its nonce before this function returns and before any route-handler work runs.
    A caller that fails later in the same request pays for that with a full
    signature-envelope rebuild (new timestamp, nonce, signature) to retry — an
    availability cost, not a security hole, and the accepted tradeoff of
    insert-or-replay nonce semantics."""
    try:
        parsed = device_sig.parse_headers(headers)
    except device_sig.MalformedSigHeaders as exc:
        raise AgentUnauthenticated("malformed device-signature headers") from exc

    device_id = UUID(parsed.device_id)
    if expected_agent_id is not None and device_id != expected_agent_id:
        raise AgentUnauthenticated("X-Device-Id does not match expected agent")

    agent = session.get(Agent, device_id)
    if agent is None:
        raise AgentUnauthenticated("unknown device")

    if agent.revoked_at is not None:
        raise AgentRevoked("device is revoked")

    try:
        timestamp = device_sig.parse_timestamp(parsed.timestamp)
    except device_sig.MalformedSigHeaders as exc:
        raise AgentUnauthenticated("malformed X-Timestamp") from exc

    skew = get_settings().device_sig_max_skew_seconds
    if abs((now - timestamp).total_seconds()) > skew:
        raise AgentUnauthenticated("timestamp outside allowed skew")

    computed_body_hash = device_sig.body_sha256(body)
    if not hmac.compare_digest(computed_body_hash, parsed.body_sha256):
        raise AgentUnauthenticated("body hash mismatch")

    canonical = device_sig.canonical_string(
        method,
        path,
        parsed.device_id,
        parsed.timestamp,
        parsed.nonce,
        parsed.body_sha256,
    )
    try:
        device_sig.verify(agent.public_key, canonical, parsed.signature)
    except device_sig.SignatureError as exc:
        raise AgentUnauthenticated("signature verification failed") from exc

    prune_expired_nonces(session, now=now)
    try:
        remember_nonce(
            session,
            agent_id=agent.id,
            nonce=parsed.nonce,
            expires_at=timestamp + timedelta(seconds=skew),
        )
    except NonceReplayError as exc:
        raise AgentUnauthenticated("nonce already used") from exc

    return AgentIdentity(agent_id=agent.id, org_id=agent.org_id)


async def require_agent(
    request: Request, session: Session = Depends(get_session)
) -> AgentIdentity:
    body = await request.body()
    try:
        return authenticate_agent(
            session,
            method=request.method,
            path=request.url.path,
            headers=request.headers,
            body=body,
            now=utc_now(),
        )
    except AgentRevoked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AgentUnauthenticated as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def require_agent_ws(
    websocket: WebSocket,
    agent_id: UUID,
    session: Session = Depends(get_session),
) -> AgentIdentity:
    try:
        return authenticate_agent(
            session,
            method="GET",
            path=websocket.url.path,
            headers=websocket.headers,
            body=b"",
            now=utc_now(),
            expected_agent_id=agent_id,
        )
    except AgentRevoked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AgentUnauthenticated as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
