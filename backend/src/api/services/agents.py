from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from api.models.command import Agent
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
        "target_subnet": agent.target_subnet,
        "active_command_id": None if active is None else active.id,
    }


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
