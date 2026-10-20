from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, constr

from api.schemas.agent_updates import AgentUpdateHelloContext
from api.schemas.commands import NspiOptions
from api.schemas.scan import ScanMode, SubnetCIDR
from api.schemas.scan_progress import ScanProgressSnapshot

AgentStatus = Literal["running", "uploading", "done", "failed", "cancelled"]


class AvailableSubnet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface: constr(min_length=1)
    cidr: SubnetCIDR
    is_default_route: bool


class AgentHelloFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hello"]
    agent_version: str
    available_subnets: list[AvailableSubnet]
    package_version: str | None = None
    updater_version: str | None = None
    os_suite: str | None = None
    architecture: str | None = None
    capabilities: list[Literal["scan_finalization_v1", "agent_update_v1"]] = Field(
        default_factory=list
    )
    update_context: AgentUpdateHelloContext | None = None


class UpdateSessionFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_session"]
    session_id: UUID
    protocol_version: Literal[1]
    capabilities: list[Literal["scan_finalization_v1", "agent_update_v1"]]


class AgentUpdateFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["agent_update"]
    update_id: UUID
    session_id: UUID
    release_id: UUID
    target_package_version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime


class ScanStatusAckFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["scan_status_ack"]
    session_id: UUID
    command_id: UUID
    status: Literal["done", "failed", "cancelled", "expired"]
    has_results: bool


class AgentStatusFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["status"]
    command_id: UUID
    status: AgentStatus
    error_code: str | None = None


class AgentProgressFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["progress"]
    command_id: UUID
    scan_id: UUID
    sequence: Annotated[int, Field(ge=1)]
    progress: ScanProgressSnapshot


class AgentCommandFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["command"]
    command_id: UUID
    scan_id: UUID
    scan_mode: ScanMode
    subnet: SubnetCIDR
    nspi_options: NspiOptions | None = None


class AgentCancelFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["cancel"]
    command_id: UUID


class AgentErrorFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["error"]
    message: str
