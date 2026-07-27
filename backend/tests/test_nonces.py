from __future__ import annotations

from datetime import timedelta

from api.models.command import Agent, AgentNonce
from api.models.identity import Org
from api.models.persistence import utc_now
from api.services.nonces import NonceReplayError, prune_expired_nonces, remember_nonce
from sqlmodel import Session, select


def _seed_agent(session: Session, *, name: str = "agent-1") -> Agent:
    org = Org(name="Test Org")
    session.add(org)
    session.commit()
    session.refresh(org)
    agent = Agent(org_id=org.id, display_name=name, public_key=b"\x01" * 32)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def test_remember_nonce_then_replay_raises(administrative_session: Session) -> None:
    agent = _seed_agent(administrative_session)
    expires_at = utc_now() + timedelta(minutes=5)

    remember_nonce(
        administrative_session, agent_id=agent.id, nonce="abc", expires_at=expires_at
    )

    try:
        remember_nonce(
            administrative_session,
            agent_id=agent.id,
            nonce="abc",
            expires_at=expires_at,
        )
    except NonceReplayError:
        pass
    else:
        raise AssertionError("expected NonceReplayError")


def test_same_nonce_different_agents_both_succeed(
    administrative_session: Session,
) -> None:
    agent_one = _seed_agent(administrative_session, name="agent-1")
    agent_two = _seed_agent(administrative_session, name="agent-2")
    expires_at = utc_now() + timedelta(minutes=5)

    remember_nonce(
        administrative_session,
        agent_id=agent_one.id,
        nonce="shared",
        expires_at=expires_at,
    )
    remember_nonce(
        administrative_session,
        agent_id=agent_two.id,
        nonce="shared",
        expires_at=expires_at,
    )

    rows = administrative_session.exec(select(AgentNonce)).all()
    assert len(rows) == 2


def test_session_usable_after_replay_error(administrative_session: Session) -> None:
    agent = _seed_agent(administrative_session)
    expires_at = utc_now() + timedelta(minutes=5)

    remember_nonce(
        administrative_session, agent_id=agent.id, nonce="one", expires_at=expires_at
    )
    try:
        remember_nonce(
            administrative_session,
            agent_id=agent.id,
            nonce="one",
            expires_at=expires_at,
        )
    except NonceReplayError:
        pass

    remember_nonce(
        administrative_session, agent_id=agent.id, nonce="two", expires_at=expires_at
    )

    rows = administrative_session.exec(select(AgentNonce)).all()
    assert len(rows) == 2


def test_remember_nonce_stores_given_expires_at_verbatim(
    administrative_session: Session,
) -> None:
    agent = _seed_agent(administrative_session)
    given_expires_at = utc_now() - timedelta(days=1)

    remember_nonce(
        administrative_session,
        agent_id=agent.id,
        nonce="past-expiry",
        expires_at=given_expires_at,
    )

    stored = administrative_session.exec(
        select(AgentNonce).where(AgentNonce.nonce == "past-expiry")
    ).one()
    assert stored.expires_at == given_expires_at


def test_prune_expired_nonces_deletes_only_strictly_past(
    administrative_session: Session,
) -> None:
    agent = _seed_agent(administrative_session)
    now = utc_now()

    expired = AgentNonce(
        agent_id=agent.id, nonce="expired", expires_at=now - timedelta(seconds=1)
    )
    boundary = AgentNonce(agent_id=agent.id, nonce="boundary", expires_at=now)
    fresh = AgentNonce(
        agent_id=agent.id, nonce="fresh", expires_at=now + timedelta(minutes=5)
    )
    administrative_session.add(expired)
    administrative_session.add(boundary)
    administrative_session.add(fresh)
    administrative_session.commit()

    prune_expired_nonces(administrative_session, now=now)

    remaining = {
        row.nonce
        for row in administrative_session.exec(select(AgentNonce)).all()
    }
    assert remaining == {"boundary", "fresh"}
