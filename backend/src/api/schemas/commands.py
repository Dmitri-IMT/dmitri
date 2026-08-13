from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from api.core.error_codes import ScanErrorCode
from api.schemas.scan import ScanMode, SubnetCIDR

CommandStatus = Literal[
    "queued",
    "delivered",
    "running",
    "uploading",
    "done",
    "failed",
    "expired",
]


class CreateCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_mode: ScanMode
    subnet: SubnetCIDR


class CommandSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    scan_id: UUID | None = None
    agent_id: UUID
    status: CommandStatus


class CommandDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    scan_id: UUID | None = None
    agent_id: UUID
    scan_mode: ScanMode
    subnet: str
    status: CommandStatus
    error_code: ScanErrorCode | None = None
    created_at: datetime
    delivered_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
