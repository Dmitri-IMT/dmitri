from __future__ import annotations

import secrets
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select, update
from starlette.concurrency import run_in_threadpool

from api.models.command import Agent
from api.models.identity import Org
from api.schemas.agents import AgentDetail, AgentSummary
from api.services import agent_connections
from api.services.commands import SubnetNotReportedError, active_command_for


class AgentOfflineError(Exception):
    pass


def _fields(session: Session, agent: Agent) -> dict[str, object]:
    active = active_command_for(session, agent.id)
    return {
        "agent_id": agent.id,
        "display_name": agent.display_name,
        "online": agent_connections.is_online(agent.id),
        "last_seen_at": agent_connections.last_seen_at(agent.id) or agent.last_seen_at,
        "revoked_at": agent.revoked_at,
        "target_subnet": agent.target_subnet,
        "active_command_id": None if active is None else active.id,
    }


def register_agent(
    session: Session, *, org: Org, display_name: str, public_key: bytes
) -> Agent:
    """Register once per org/key; retries preserve identity and revocation."""
    if org.ot_digest_key is None:
        session.exec(
            update(Org)
            .where(Org.id == org.id, Org.ot_digest_key.is_(None))
            .values(ot_digest_key=secrets.token_hex(32))
        )
    session.execute(
        insert(Agent)
        .values(org_id=org.id, display_name=display_name, public_key=public_key)
        .on_conflict_do_nothing(constraint="uq_agents_org_public_key")
    )
    agent = session.exec(
        select(Agent).where(Agent.org_id == org.id, Agent.public_key == public_key)
    ).one()
    session.commit()
    session.refresh(agent)
    return agent


def list_agents(session: Session, *, org_id: UUID) -> list[AgentSummary]:
    agents = session.exec(
        select(Agent)
        .where(Agent.org_id == org_id)
        .order_by(Agent.created_at.asc(), Agent.id.asc())
    ).all()
    return [AgentSummary(**_fields(session, agent)) for agent in agents]


def _agent(session: Session, agent_id: UUID, org_id: UUID) -> Agent | None:
    return session.exec(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == org_id)
    ).first()


def _detail(session: Session, agent: Agent) -> AgentDetail:
    hello = agent_connections.get_hello(agent.id)
    return AgentDetail(
        **_fields(session, agent),
        available_subnets=[] if hello is None else hello[1],
        observed_version=agent.observed_version,
        observed_package_version=agent.observed_package_version,
        version_observed_at=agent.version_observed_at,
    )


def get_agent_detail(
    session: Session, *, agent_id: UUID, org_id: UUID
) -> AgentDetail | None:
    agent = _agent(session, agent_id, org_id)
    if agent is None:
        return None
    return _detail(session, agent)


def set_target_subnet(
    session: Session, *, agent_id: UUID, org_id: UUID, target_subnet: str
) -> AgentDetail | None:
    agent = _agent(session, agent_id, org_id)
    if agent is None:
        return None
    hello = agent_connections.get_hello(agent.id)
    if hello is None:
        raise AgentOfflineError
    if target_subnet not in {entry.cidr for entry in hello[1]}:
        raise SubnetNotReportedError
    agent.target_subnet = target_subnet
    session.add(agent)
    session.commit()
    return _detail(session, agent)


def _set_revoked_at(
    session: Session, *, agent_id: UUID, org_id: UUID, revoked_at: datetime | None
) -> AgentDetail | None:
    agent = _agent(session, agent_id, org_id)
    if agent is None:
        return None
    if (agent.revoked_at is None) != (revoked_at is None):
        agent.revoked_at = revoked_at
        session.add(agent)
        session.commit()
    return _detail(session, agent)


async def revoke_agent(
    session: Session, *, agent_id: UUID, org_id: UUID, now: datetime
) -> AgentDetail | None:
    """Mark the agent revoked, keeping the first timestamp, then drop its socket.

    The write commits before the close, so the Pi cannot reconnect in between.
    """
    detail = await run_in_threadpool(
        _set_revoked_at, session, agent_id=agent_id, org_id=org_id, revoked_at=now
    )
    if detail is not None:
        socket = agent_connections.get_socket(agent_id)
        if socket is not None:
            await agent_connections.close_revoked(socket)
    return detail


def restore_agent(
    session: Session, *, agent_id: UUID, org_id: UUID
) -> AgentDetail | None:
    return _set_revoked_at(session, agent_id=agent_id, org_id=org_id, revoked_at=None)
