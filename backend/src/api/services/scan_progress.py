from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlmodel import Session, select

from api.models.command import Command
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AgentProgressFrame

ProgressApplyResult = Literal["ok", "unknown_command"]
_ACTIVE_COMMAND_STATUSES = ("running", "uploading")
_TERMINAL_SCAN_STATUSES = ("completed", "failed", "cancelled")


def apply_progress(
    session: Session,
    *,
    agent_id: UUID,
    frame: AgentProgressFrame,
    now: datetime,
    commit: bool = True,
) -> ProgressApplyResult:
    """Persist only a newer snapshot for the matching active command and scan."""
    command = session.exec(
        select(Command)
        .where(Command.id == frame.command_id, Command.agent_id == agent_id)
        .with_for_update()
    ).first()
    if command is None:
        session.rollback()
        return "unknown_command"

    if (
        command.scan_id != frame.scan_id
        or command.status not in _ACTIVE_COMMAND_STATUSES
    ):
        session.rollback()
        return "ok"

    scan = session.exec(
        select(ScanRecord)
        .where(ScanRecord.scan_id == frame.scan_id, ScanRecord.agent_id == agent_id)
        .with_for_update()
    ).first()
    if scan is None or scan.status in _TERMINAL_SCAN_STATUSES:
        session.rollback()
        return "ok"
    if frame.sequence <= scan.progress_seq:
        session.rollback()
        return "ok"

    scan.progress_json = frame.progress.model_dump(mode="json")
    scan.progress_seq = frame.sequence
    scan.progress_updated_at = now
    session.add(scan)
    if commit:
        session.commit()
    return "ok"
