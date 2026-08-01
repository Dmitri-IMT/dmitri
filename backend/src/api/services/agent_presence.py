from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from api.db.session import get_engine
from api.models.command import Agent

SessionFactory = Callable[[], Session]


def default_session_factory() -> Session:
    return Session(get_engine())


def touch_agent_last_seen(session: Session, agent_id: UUID, now: datetime) -> None:
    agent = session.get(Agent, agent_id)
    if agent is None:
        return
    agent.last_seen_at = now
    session.commit()


def mark_connected(session: Session, agent_id: UUID, now: datetime) -> None:
    agent = session.get(Agent, agent_id)
    if agent is None:
        return
    agent.connected_at = now
    agent.last_seen_at = now
    session.commit()


def mark_disconnected(session: Session, agent_id: UUID) -> None:
    agent = session.get(Agent, agent_id)
    if agent is None:
        return
    agent.connected_at = None
    session.commit()


def reconcile_all(session: Session) -> None:
    session.execute(update(Agent).values(connected_at=None))
    session.commit()


async def async_touch_agent_last_seen(
    session_factory: SessionFactory,
    agent_id: UUID,
    now: datetime,
) -> None:
    def sync_work() -> None:
        session = session_factory()
        try:
            touch_agent_last_seen(session, agent_id, now)
        finally:
            session.close()

    await run_in_threadpool(sync_work)


async def async_mark_connected(
    session_factory: SessionFactory,
    agent_id: UUID,
    now: datetime,
) -> None:
    def sync_work() -> None:
        session = session_factory()
        try:
            mark_connected(session, agent_id, now)
        finally:
            session.close()

    await run_in_threadpool(sync_work)


async def async_mark_disconnected(
    session_factory: SessionFactory,
    agent_id: UUID,
) -> None:
    def sync_work() -> None:
        session = session_factory()
        try:
            mark_disconnected(session, agent_id)
        finally:
            session.close()

    await run_in_threadpool(sync_work)
