from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.agent_auth import AgentIdentity, require_agent
from api.schemas.agent_updates import AgentProtocolSupport

router = APIRouter()


@router.get(
    "/api/v1/agents/{agent_id}/update-protocol",
    response_model=AgentProtocolSupport,
    operation_id="getAgentUpdateProtocol",
)
def read_agent_update_protocol(
    agent_id: UUID,
    identity: AgentIdentity = Depends(require_agent),
) -> AgentProtocolSupport:
    if identity.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentProtocolSupport(
        protocol_versions=[1], capabilities=["scan_finalization_v1"]
    )
