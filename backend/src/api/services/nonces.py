from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete

from api.models.command import AgentNonce


class NonceReplayError(ValueError):
    pass


def remember_nonce(
    session: Session, *, agent_id: UUID, nonce: str, expires_at: datetime
) -> None:
    session.add(AgentNonce(agent_id=agent_id, nonce=nonce, expires_at=expires_at))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise NonceReplayError("nonce already used for this agent") from exc


def prune_expired_nonces(session: Session, *, now: datetime) -> None:
    session.exec(delete(AgentNonce).where(AgentNonce.expires_at < now))
    session.commit()
