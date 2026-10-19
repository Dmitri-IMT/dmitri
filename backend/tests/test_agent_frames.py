from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pydantic
import pytest
import yaml
from api.schemas.agent_frames import (
    AgentCommandFrame,
    AgentErrorFrame,
    AgentHelloFrame,
    AgentStatusFrame,
    AvailableSubnet,
    ScanStatusAckFrame,
    UpdateSessionFrame,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "openapi" / "openapi.yaml"
)

COMMAND_ID = UUID("11111111-1111-4111-8111-111111111111")
SCAN_ID = UUID("22222222-2222-4222-8222-222222222222")


def test_hello_frame_validates_good_payload():
    frame = AgentHelloFrame.model_validate(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": [
                {
                    "interface": "eth0",
                    "cidr": "10.0.0.0/24",
                    "is_default_route": False,
                },
                {
                    "interface": "wlan0",
                    "cidr": "192.168.1.0/24",
                    "is_default_route": True,
                },
            ],
        }
    )

    assert frame.type == "hello"
    assert frame.agent_version == "0.2.0"
    assert len(frame.available_subnets) == 2
    assert frame.available_subnets[0].interface == "eth0"
    assert frame.available_subnets[0].cidr == "10.0.0.0/24"
    assert frame.available_subnets[0].is_default_route is False
    assert frame.available_subnets[1].is_default_route is True


def test_hello_frame_rejects_subnet_without_is_default_route():
    with pytest.raises(pydantic.ValidationError):
        AgentHelloFrame.model_validate(
            {
                "type": "hello",
                "agent_version": "0.2.0",
                "available_subnets": [
                    {"interface": "eth0", "cidr": "10.0.0.0/24"},
                ],
            }
        )


@pytest.mark.parametrize("flag", [None, "maybe", {}, []])
def test_hello_frame_rejects_non_boolean_is_default_route(flag):
    with pytest.raises(pydantic.ValidationError):
        AgentHelloFrame.model_validate(
            {
                "type": "hello",
                "agent_version": "0.2.0",
                "available_subnets": [
                    {
                        "interface": "eth0",
                        "cidr": "10.0.0.0/24",
                        "is_default_route": flag,
                    },
                ],
            }
        )


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


@pytest.mark.parametrize(
    ("schema_name", "model"),
    [
        ("AvailableSubnet", AvailableSubnet),
        ("AgentHelloFrame", AgentHelloFrame),
        ("AgentCommandFrame", AgentCommandFrame),
        ("AgentStatusFrame", AgentStatusFrame),
        ("UpdateSessionFrame", UpdateSessionFrame),
        ("ScanStatusAckFrame", ScanStatusAckFrame),
        ("AgentErrorFrame", AgentErrorFrame),
    ],
)
def test_frame_models_match_the_contract(schema_name, model):
    spec = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = spec["components"]["schemas"][schema_name]

    assert schema["additionalProperties"] is False
    assert set(model.model_fields) == set(schema["properties"])
    assert set(schema["required"]) <= set(model.model_fields)
