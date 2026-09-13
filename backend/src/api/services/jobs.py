from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, or_
from sqlmodel import Session, select


def claim_jobs(
    session: Session,
    model: Any,
    *,
    running_status: str,
    exhausted_error: str,
    batch_size: int,
    max_attempts: int,
    stale_after_seconds: float,
    now: datetime,
    where: ColumnElement[bool] | None = None,
) -> list[Any]:
    stale_before = now - timedelta(seconds=stale_after_seconds)

    exhausted = session.exec(
        select(model).where(
            model.status == running_status,
            model.started_at <= stale_before,
            model.attempts >= max_attempts,
        )
    ).all()
    for job in exhausted:
        job.status = "failed"
        job.completed_at = now
        job.last_error = exhausted_error
        session.add(job)
    if exhausted:
        session.commit()

    eligible_pending = (
        (model.status == "pending")
        & (model.attempts < max_attempts)
        & or_(model.next_attempt_at.is_(None), model.next_attempt_at <= now)
    )
    eligible_stale = (
        (model.status == running_status)
        & (model.attempts < max_attempts)
        & (model.started_at <= stale_before)
    )
    statement = select(model).where(or_(eligible_pending, eligible_stale))
    if where is not None:
        statement = statement.where(where)
    statement = statement.order_by(model.created_at, model.id).limit(batch_size)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    jobs = session.exec(statement).all()
    for job in jobs:
        job.status = running_status
        job.attempts += 1
        job.started_at = now
        job.next_attempt_at = None
        job.completed_at = None
        job.last_error = None
        session.add(job)
    session.commit()
    for job in jobs:
        session.refresh(job)
    return list(jobs)


def retry_or_fail(
    job: Any,
    *,
    error: str,
    retryable: bool,
    max_attempts: int,
    delay_seconds: float,
    now: datetime,
) -> None:
    if retryable and job.attempts < max_attempts:
        job.status = "pending"
        job.next_attempt_at = now + timedelta(seconds=delay_seconds)
        job.completed_at = None
    else:
        job.status = "failed"
        job.next_attempt_at = None
        job.completed_at = now
    job.last_error = error
