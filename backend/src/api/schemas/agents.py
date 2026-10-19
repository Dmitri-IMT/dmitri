from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.agent_frames import AvailableSubnet
from api.schemas.scan import SubnetCIDR


class AgentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    display_name: str
    online: bool
    last_seen_at: datetime | None
    revoked_at: datetime | None
    target_subnet: SubnetCIDR | None = None
    active_command_id: UUID | None = None


class AgentDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    display_name: str
    online: bool
    last_seen_at: datetime | None
    revoked_at: datetime | None
    available_subnets: list[AvailableSubnet]
    observed_version: str | None = None
    observed_package_version: str | None = None
    version_observed_at: datetime | None = None
    target_subnet: SubnetCIDR | None = None
    active_command_id: UUID | None = None


class RegisterAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[str, Field(min_length=1)]
    # Raw 32-byte Ed25519 public key, hex-encoded.
    public_key: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]


class RegisterAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID


class AgentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[AgentSummary]


class UpdateAgentTargetSubnetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_subnet: SubnetCIDR
