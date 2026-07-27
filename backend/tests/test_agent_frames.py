from __future__ import annotations

from uuid import UUID

import pydantic
import pytest
from api.schemas.agent_frames import (
    AgentCommandFrame,
    AgentErrorFrame,
    AgentHelloFrame,
    AgentStatusFrame,
)

COMMAND_ID = UUID("11111111-1111-4111-8111-111111111111")
SCAN_ID = UUID("22222222-2222-4222-8222-222222222222")


def test_hello_frame_validates_good_payload():
    frame = AgentHelloFrame.model_validate(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": [{"interface": "eth0", "cidr": "10.0.0.0/24"}],
        }
    )

    assert frame.type == "hello"
    assert frame.agent_version == "0.2.0"
    assert len(frame.available_subnets) == 1
    assert frame.available_subnets[0].interface == "eth0"
    assert frame.available_subnets[0].cidr == "10.0.0.0/24"


def test_status_frame_validates_good_payload():
    frame = AgentStatusFrame.model_validate(
        {
            "type": "status",
            "command_id": str(COMMAND_ID),
            "status": "running",
        }
    )

    assert frame.type == "status"
    assert frame.command_id == COMMAND_ID
    assert frame.status == "running"
    assert frame.error_code is None


def test_status_frame_accepts_error_code():
    frame = AgentStatusFrame.model_validate(
        {
            "type": "status",
            "command_id": str(COMMAND_ID),
            "status": "failed",
            "error_code": "scan_timeout",
        }
    )

    assert frame.error_code == "scan_timeout"


def test_status_frame_rejects_unknown_status():
    with pytest.raises(pydantic.ValidationError):
        AgentStatusFrame.model_validate(
            {
                "type": "status",
                "command_id": str(COMMAND_ID),
                "status": "queued",
            }
        )


def test_hello_frame_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        AgentHelloFrame.model_validate(
            {
                "type": "hello",
                "agent_version": "0.2.0",
                "available_subnets": [],
                "extra": True,
            }
        )


def test_status_frame_rejects_missing_required_field():
    with pytest.raises(pydantic.ValidationError):
        AgentStatusFrame.model_validate(
            {
                "type": "status",
                "status": "running",
            }
        )


def test_command_frame_validates_good_payload():
    frame = AgentCommandFrame.model_validate(
        {
            "type": "command",
            "command_id": str(COMMAND_ID),
            "scan_id": str(SCAN_ID),
            "scan_mode": "standard",
            "subnet": "10.0.0.0/24",
        }
    )

    assert frame.type == "command"
    assert frame.command_id == COMMAND_ID
    assert frame.scan_id == SCAN_ID
    assert frame.scan_mode == "standard"
    assert frame.subnet == "10.0.0.0/24"


def test_error_frame_validates_good_payload():
    frame = AgentErrorFrame.model_validate({"type": "error", "message": "bad frame"})

    assert frame.type == "error"
    assert frame.message == "bad frame"
