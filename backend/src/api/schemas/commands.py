from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.core.error_codes import ScanErrorCode
from api.schemas.scan import ScanMode, SubnetCIDR

CommandStatus = Literal[
    "queued",
    "delivered",
    "running",
    "uploading",
    "done",
    "failed",
    "cancelled",
    "expired",
]

NspiSubmode = Literal["inventory", "read_only_mapping", "active_validation"]


class NspiOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    submode: NspiSubmode = "inventory"
    active_risk_acknowledged: bool = False
    change_ticket: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_active_confirmation(self) -> NspiOptions:
        if self.submode == "active_validation":
            if not self.active_risk_acknowledged:
                raise ValueError("active_validation requires risk acknowledgement")
            if self.change_ticket is None:
                raise ValueError("active_validation requires a change_ticket")
        elif self.active_risk_acknowledged or self.change_ticket is not None:
            raise ValueError(
                "active acknowledgement and change_ticket require active_validation"
            )
        return self


class CreateCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_mode: ScanMode
    subnet: SubnetCIDR
    nspi_options: NspiOptions | None = None

    @model_validator(mode="after")
    def validate_nspi_options(self) -> CreateCommandRequest:
        if self.scan_mode != "nspi" and self.nspi_options is not None:
            raise ValueError("nspi_options requires scan_mode='nspi'")
        return self


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
    nspi_options: NspiOptions | None = None
    status: CommandStatus
    error_code: ScanErrorCode | None = None
    created_at: datetime
    delivered_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # True once ingest completed the scan, including a stopped scan's partial results.
    has_results: bool = False
