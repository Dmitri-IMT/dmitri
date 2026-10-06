from __future__ import annotations

from uuid import uuid4

import pytest
from api.schemas.agent_frames import AgentProgressFrame
from api.schemas.scan_progress import ScanProgressSnapshot
from pydantic import ValidationError


def _snapshot(**overrides: object) -> dict[str, object]:
    return {
        "stage": "discovery",
        "percent": 0,
        "machines": None,
        "open_ports": None,
        "filtered_ports": None,
        "industrial_services": None,
        "vulnerabilities": None,
        **overrides,
    }


def test_progress_snapshot_accepts_unknown_counts_and_confirmed_zero() -> None:
    snapshot = ScanProgressSnapshot.model_validate(
        _snapshot(machines=0, open_ports=0)
    )

    assert snapshot.machines == 0
    assert snapshot.open_ports == 0
    assert snapshot.filtered_ports is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"stage": "unknown"},
        {"percent": -1},
        {"percent": 100},
        {"machines": -1},
        {"extra": True},
    ],
)
def test_progress_snapshot_rejects_invalid_values(overrides) -> None:
    with pytest.raises(ValidationError):
        ScanProgressSnapshot.model_validate(_snapshot(**overrides))


def test_agent_progress_frame_requires_identity_sequence_and_snapshot() -> None:
    frame = AgentProgressFrame.model_validate(
        {
            "type": "progress",
            "command_id": str(uuid4()),
            "scan_id": str(uuid4()),
            "sequence": 1,
            "progress": _snapshot(),
        }
    )

    assert frame.sequence == 1
    assert frame.progress.stage == "discovery"


def test_agent_progress_frame_rejects_nonpositive_sequence() -> None:
    with pytest.raises(ValidationError):
        AgentProgressFrame.model_validate(
            {
                "type": "progress",
                "command_id": str(uuid4()),
                "scan_id": str(uuid4()),
                "sequence": 0,
                "progress": _snapshot(),
            }
        )
