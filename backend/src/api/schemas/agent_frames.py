from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, constr

from api.schemas.scan import ScanMode, SubnetCIDR

AgentStatus = Literal["running", "uploading", "done", "failed"]


class AvailableSubnet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface: constr(min_length=1)
    cidr: SubnetCIDR


class AgentHelloFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hello"]
    agent_version: str
    available_subnets: list[AvailableSubnet]


class AgentStatusFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["status"]
    command_id: UUID
    status: AgentStatus
    error_code: str | None = None


class AgentCommandFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["command"]
    command_id: UUID
    scan_id: UUID
    scan_mode: ScanMode
    subnet: SubnetCIDR


class AgentErrorFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["error"]
    message: str
