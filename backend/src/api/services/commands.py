from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select
from starlette.concurrency import run_in_threadpool

from api.core.config import get_settings
from api.core.error_codes import normalise_error_code
from api.models.command import Agent, Command
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AgentCancelFrame, AgentCommandFrame
from api.schemas.commands import CommandDetail
from api.services import agent_connections, agent_presence
from api.services.activity import append_scan_activity
from api.services.command_lifecycle import (
    NON_TERMINAL,
    PI_OWNED,
    RANK,
    is_terminal,
    scan_status_for,
    status_rank,
)

logger = logging.getLogger(__name__)


class DeviceOfflineError(Exception):
    pass


class DeviceBusyError(Exception):
    pass


class AgentNotFoundError(Exception):
    pass


class SubnetNotReportedError(Exception):
    pass


class CommandNotCancellableError(Exception):
    pass


_STATUS_RANK = case(
    *[(Command.status == status, rank) for status, rank in RANK.items()],
    else_=max(RANK.values()),
)


def enqueue(
    session: Session,
    *,
    org_id: UUID,
    agent_id: UUID,
    scan_mode: str,
    subnet: str,
    nspi_options: dict[str, object] | None = None,
    now: datetime,
) -> Command:
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_mode=scan_mode,
        subnet=subnet,
        nspi_options=nspi_options,
        status="queued",
        created_at=now,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def get_command_detail(
    session: Session, command_id: UUID, *, org_id: UUID
) -> CommandDetail | None:
    command = session.exec(
        select(Command).where(Command.id == command_id, Command.org_id == org_id)
    ).first()
    if command is None:
        return None
    return _command_detail(command)


def cancelled_command_ids_for_agent(
    session: Session, *, agent_id: UUID, now: datetime
) -> list[UUID]:
    deadline_by_mode = {
        mode: now - timedelta(seconds=seconds)
        for mode, seconds in get_settings().command_max_duration_by_mode().items()
    }
    return list(
        session.exec(
            select(Command.id)
            .join(ScanRecord, ScanRecord.scan_id == Command.scan_id)
            .where(
                Command.agent_id == agent_id,
                Command.status == "cancelled",
                ScanRecord.status == "cancelled",
                func.coalesce(Command.delivered_at, Command.created_at)
                >= case(deadline_by_mode, value=Command.scan_mode),
            )
        ).all()
    )


def _command_detail(command: Command) -> CommandDetail:
    return CommandDetail(
        command_id=command.id,
        scan_id=command.scan_id,
        agent_id=command.agent_id,
        scan_mode=command.scan_mode,
        subnet=command.subnet,
        nspi_options=command.nspi_options,
        status=command.status,
        error_code=normalise_error_code(command.error_code),
        created_at=command.created_at,
        delivered_at=command.delivered_at,
        started_at=command.started_at,
        completed_at=command.completed_at,
    )


def _inspect_command_for_cancel(
    session: Session, *, command_id: UUID, org_id: UUID
) -> CommandDetail | None:
    command = session.exec(
        select(Command).where(Command.id == command_id, Command.org_id == org_id)
    ).first()
    detail = _command_detail(command) if command is not None else None
    session.rollback()
    return detail


def _retire_offline_command(
    session: Session,
    *,
    command_id: UUID,
    org_id: UUID,
    now: datetime,
) -> tuple[CommandDetail, int] | None:
    cancellable = tuple(status for status in NON_TERMINAL if status != "uploading")
    rows = _retire_commands(
        session,
        [
            Command.id == command_id,
            Command.org_id == org_id,
            Command.status.in_(cancellable),
        ],
        values={"status": "cancelled", "completed_at": now, "error_code": None},
    )
    if rows:
        _mirror_retired_commands(session, rows, now=now)
        session.commit()
    else:
        session.rollback()

    detail = get_command_detail(session, command_id, org_id=org_id)
    if detail is None:
        return None
    if detail.status == "uploading":
        raise CommandNotCancellableError
    return detail, 200


async def cancel_command(
    session: Session,
    *,
    org_id: UUID,
    command_id: UUID,
    now: datetime,
) -> tuple[CommandDetail, int] | None:
    detail = await run_in_threadpool(
        _inspect_command_for_cancel,
        session,
        command_id=command_id,
        org_id=org_id,
    )
    if detail is None:
        return None
    if is_terminal(detail.status):
        return detail, 200
    if detail.status == "uploading":
        raise CommandNotCancellableError

    socket = agent_connections.get_socket(detail.agent_id)
    if socket is not None:
        frame = AgentCancelFrame(type="cancel", command_id=command_id)
        try:
            await socket.send_text(frame.model_dump_json())
        except Exception:
            logger.exception("Failed to send cancel for command %s", command_id)
        else:
            return detail, 202

    return await run_in_threadpool(
        _retire_offline_command,
        session,
        command_id=command_id,
        org_id=org_id,
        now=now,
    )


def active_command_for(session: Session, agent_id: UUID) -> Command | None:
    return session.exec(
        select(Command)
        .where(Command.agent_id == agent_id)
        .where(Command.status.in_(NON_TERMINAL))
    ).first()


def command_for_scan(session: Session, scan_id: UUID) -> Command | None:
    return session.exec(select(Command).where(Command.scan_id == scan_id)).first()


def apply_status(
    session: Session,
    *,
    agent_id: UUID,
    command_id: UUID,
    status: str,
    now: datetime,
    error_code: str | None = None,
) -> bool:
    if status not in PI_OWNED:
        return False

    next_rank = status_rank(status)
    values: dict[str, object] = {"status": status}
    if next_rank >= status_rank("running"):
        values["started_at"] = func.coalesce(Command.started_at, now)
        values["delivered_at"] = func.coalesce(Command.delivered_at, now)
    if is_terminal(status):
        values["completed_at"] = func.coalesce(Command.completed_at, now)
    if status == "failed" and error_code is not None:
        values["error_code"] = error_code

    result = session.execute(
        update(Command)
        .where(
            Command.id == command_id,
            Command.agent_id == agent_id,
            _STATUS_RANK < next_rank,
            # A command with no scan_id has not been delivered yet, so a Pi-owned
            # status cannot legally apply to it — and the CHECK would reject the
            # row anyway. Excluding it here turns that into the same silent
            # zero-rowcount no-op every other lost race gets.
            Command.scan_id.is_not(None),
        )
        .values(**values)
        .returning(Command.scan_id, Command.org_id, Command.scan_mode)
    )
    row = result.first()
    if row is None:
        session.rollback()
        return False

    scan_id, org_id, scan_mode = row[0], row[1], row[2]
    if scan_id is not None:
        scan_update = update(ScanRecord).where(ScanRecord.scan_id == scan_id)
        if status == "cancelled":
            scan_update = scan_update.where(ScanRecord.status != "completed")
        session.execute(scan_update.values(status=scan_status_for(status)))
        if status in {"failed", "cancelled"}:
            append_scan_activity(
                session,
                org_id=org_id,
                scan_id=scan_id,
                kind=f"scan_{status}",
                scan_mode=scan_mode,
                occurred_at=now,
            )
    session.commit()
    return True


def sweep_stale_commands(
    session: Session,
    *,
    now: datetime,
    grace_seconds: int | None = None,
    agent_id: UUID | None = None,
) -> int:
    settings = get_settings()
    grace = (
        grace_seconds
        if grace_seconds is not None
        else settings.command_disconnect_grace_seconds
    )
    cutoff = now - timedelta(seconds=grace)
    non_terminal = [Command.status.in_(NON_TERMINAL)]
    if agent_id is not None:
        non_terminal.append(Command.agent_id == agent_id)

    disconnected_ids = (
        select(Command.id)
        .join(Agent, Command.agent_id == Agent.id)
        .where(
            *non_terminal,
            Agent.connected_at.is_(None),
            Agent.last_seen_at.is_not(None),
            Agent.last_seen_at < cutoff,
        )
    )
    rows = _retire_commands(
        session,
        [Command.id.in_(disconnected_ids)],
        values={
            "status": case((Command.status == "queued", "expired"), else_="failed"),
            "completed_at": case((Command.status == "queued", None), else_=now),
            "error_code": case(
                (Command.status == "queued", "device_offline"),
                else_="agent_disconnected",
            ),
        },
    )

    # Runs after the disconnect pass, so a dead agent keeps its more specific
    # reason. Only delivered commands are timed: queue wait is not scan time.
    deadline_by_mode = {
        mode: now - timedelta(seconds=seconds)
        for mode, seconds in settings.command_max_duration_by_mode().items()
    }
    rows += _retire_commands(
        session,
        [
            *non_terminal,
            Command.scan_id.is_not(None),
            func.coalesce(Command.delivered_at, Command.created_at)
            < case(deadline_by_mode, value=Command.scan_mode),
        ],
        values={"status": "failed", "completed_at": now, "error_code": "scan_timeout"},
    )
    _mirror_retired_commands(session, rows, now=now)
    if rows:
        session.commit()
    return len(rows)


def _mirror_retired_commands(session: Session, rows: list, *, now: datetime) -> None:
    for scan_id, command_status, command_org_id, command_scan_mode in rows:
        if scan_id is not None:
            scan_where = [ScanRecord.scan_id == scan_id]
            if command_status == "cancelled":
                scan_where.append(ScanRecord.status != "completed")
            session.execute(
                update(ScanRecord)
                .where(*scan_where)
                .values(status=scan_status_for(command_status))
            )
            if command_status in {"failed", "cancelled"}:
                append_scan_activity(
                    session,
                    org_id=command_org_id,
                    scan_id=scan_id,
                    kind=f"scan_{command_status}",
                    scan_mode=command_scan_mode,
                    occurred_at=now,
                )


def _retire_commands(session: Session, where: list, *, values: dict) -> list:
    return list(
        session.execute(
            update(Command)
            .where(*where)
            .values(**values)
            .returning(
                Command.scan_id,
                Command.status,
                Command.org_id,
                Command.scan_mode,
            )
        )
    )


def _expire_queued_command(session: Session, command_id: UUID) -> None:
    session.execute(
        update(Command)
        .where(Command.id == command_id, Command.status == "queued")
        # Same transition the sweep's `queued` branch takes, so it carries the
        # same reason: the Pi was not reachable to take the job.
        .values(status="expired", error_code="device_offline")
    )
    session.commit()


def _fail_unsent_command(session: Session, command_id: UUID, now: datetime) -> None:
    rows = _retire_commands(
        session,
        [Command.id == command_id, Command.status == "delivered"],
        values={
            "status": "failed",
            "completed_at": now,
            "error_code": "agent_disconnected",
        },
    )
    _mirror_retired_commands(session, rows, now=now)
    session.commit()


def _record_delivery(
    session: Session,
    *,
    command: Command,
    scan_id: UUID,
    now: datetime,
) -> Command:
    """Persist the stub scan and flip the command to `delivered`.

    Sync DB phase, run in a threadpool — never call this on the event loop.
    """
    session.add(
        ScanRecord(
            scan_id=scan_id,
            org_id=command.org_id,
            agent_id=command.agent_id,
            timestamp=now,
            subnet=command.subnet,
            scan_mode=command.scan_mode,
            status=scan_status_for("delivered"),
        )
    )
    session.flush()
    append_scan_activity(
        session,
        org_id=command.org_id,
        scan_id=scan_id,
        kind="scan_started",
        scan_mode=command.scan_mode,
        occurred_at=now,
    )
    result = session.execute(
        update(Command)
        .where(Command.id == command.id, Command.status == "queued")
        .values(status="delivered", delivered_at=now, scan_id=scan_id)
    )
    if result.rowcount == 0:
        session.rollback()
        raise DeviceOfflineError
    session.commit()
    session.refresh(command)
    return command


async def deliver(
    session: Session,
    *,
    command: Command,
    now: datetime,
) -> Command:
    socket = agent_connections.get_socket(command.agent_id)
    # Read revocation before the `or` so short-circuiting cannot hide the check:
    # an idle revoked agent has a registered socket and has sent no frame, so
    # nothing else would catch it before the command goes out.
    revoked = await run_in_threadpool(
        agent_presence.agent_is_revoked, session, command.agent_id
    )
    if revoked and socket is not None:
        await agent_connections.close_revoked(socket)
    if socket is None or revoked:
        await run_in_threadpool(_expire_queued_command, session, command.id)
        raise DeviceOfflineError

    scan_id = uuid4()
    frame = AgentCommandFrame(
        type="command",
        command_id=command.id,
        scan_id=scan_id,
        scan_mode=command.scan_mode,
        subnet=command.subnet,
        nspi_options=command.nspi_options,
    )

    command = await run_in_threadpool(
        _record_delivery, session, command=command, scan_id=scan_id, now=now
    )

    try:
        await socket.send_text(frame.model_dump_json())
    except Exception:
        logger.exception("Failed to send command %s", command.id)
        await run_in_threadpool(_fail_unsent_command, session, command.id, now)
        await run_in_threadpool(session.refresh, command)

    return command


def _claim_agent(
    session: Session,
    *,
    org_id: UUID,
    agent_id: UUID,
    scan_mode: str,
    subnet: str,
    nspi_options: dict[str, object] | None,
    now: datetime,
) -> Command:
    """Authorize the agent, retire stale rows, and insert the `queued` command.

    Sync DB phase, run in a threadpool — never call this on the event loop.
    """
    agent = session.get(Agent, agent_id)
    if agent is None or agent.org_id != org_id:
        raise AgentNotFoundError

    # A Pi that dropped off without reporting a terminal status still owns its
    # command row; retire those first so a stale row cannot wedge the device.
    sweep_stale_commands(session, now=now, agent_id=agent_id)
    if active_command_for(session, agent_id) is not None:
        raise DeviceBusyError

    hello = agent_connections.get_hello(agent_id)
    if hello is not None:
        _, reported = hello
        if subnet not in {entry.cidr for entry in reported}:
            raise SubnetNotReportedError

    try:
        return enqueue(
            session,
            org_id=org_id,
            agent_id=agent_id,
            scan_mode=scan_mode,
            subnet=subnet,
            nspi_options=nspi_options,
            now=now,
        )
    except IntegrityError as exc:
        # Lost the race with a concurrent enqueue; the index is the authority.
        session.rollback()
        raise DeviceBusyError from exc


async def enqueue_for_agent(
    session: Session,
    *,
    org_id: UUID,
    agent_id: UUID,
    scan_mode: str,
    subnet: str,
    nspi_options: dict[str, object] | None = None,
    now: datetime,
) -> Command:
    """Queue a scan on one Pi and hand it to the live command channel.

    Enforces the one-active-command-per-agent rule that the partial unique
    index in 20260731_13 backs.

    Every DB phase goes through `run_in_threadpool`: this coroutine runs on the
    event loop of a single replica, so a blocking pool wait here would stall
    every live Pi command channel (see docs/research/sync-vs-async-db-stack.md
    Caveat 2). Only the frame send actually awaits.
    """
    command = await run_in_threadpool(
        _claim_agent,
        session,
        org_id=org_id,
        agent_id=agent_id,
        scan_mode=scan_mode,
        subnet=subnet,
        nspi_options=nspi_options,
        now=now,
    )
    return await deliver(session, command=command, now=now)
