from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from api.models.command import Command
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AgentProgressFrame
from api.services.scan_progress import apply_progress
from sqlmodel import Session

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _progress_frame(command_id, scan_id, sequence: int, *, machines: int):
    return AgentProgressFrame.model_validate(
        {
            "type": "progress",
            "command_id": str(command_id),
            "scan_id": str(scan_id),
            "sequence": sequence,
            "progress": {
                "stage": "discovery",
                "percent": 10,
                "machines": machines,
                "open_ports": None,
                "filtered_ports": None,
                "industrial_services": None,
                "vulnerabilities": None,
            },
        }
    )


def _seed_scan_command(session: Session, *, org_id, agent_id, status="running"):
    scan_id = uuid4()
    scan = ScanRecord(
        scan_id=scan_id,
        org_id=org_id,
        agent_id=agent_id,
        timestamp=NOW,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="accepted",
    )
    session.add(scan)
    session.flush()
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status=status,
    )
    session.add(command)
    session.commit()
    session.refresh(scan)
    session.refresh(command)
    return scan, command


def test_apply_progress_stores_latest_sequence_and_server_time(
    administrative_session: Session, seeded_org, provisioned_agent
) -> None:
    scan, command = _seed_scan_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )

    outcome = apply_progress(
        administrative_session,
        agent_id=provisioned_agent.id,
        frame=_progress_frame(command.id, scan.scan_id, 1, machines=3),
        now=NOW,
    )

    administrative_session.refresh(scan)
    assert outcome == "ok"
    assert scan.progress_json is not None
    assert scan.progress_json["machines"] == 3
    assert scan.progress_seq == 1
    assert scan.progress_updated_at == NOW


def test_apply_progress_ignores_duplicate_and_older_sequences(
    administrative_session: Session, seeded_org, provisioned_agent
) -> None:
    scan, command = _seed_scan_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    apply_progress(
        administrative_session,
        agent_id=provisioned_agent.id,
        frame=_progress_frame(command.id, scan.scan_id, 2, machines=8),
        now=NOW,
    )

    for sequence in (2, 1):
        assert apply_progress(
            administrative_session,
            agent_id=provisioned_agent.id,
            frame=_progress_frame(command.id, scan.scan_id, sequence, machines=1),
            now=NOW,
        ) == "ok"

    administrative_session.refresh(scan)
    assert scan.progress_json["machines"] == 8
    assert scan.progress_seq == 2


def test_apply_progress_ignores_wrong_scan_and_terminal_command(
    administrative_session: Session, seeded_org, provisioned_agent
) -> None:
    scan, command = _seed_scan_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    wrong_scan = uuid4()
    assert apply_progress(
        administrative_session,
        agent_id=provisioned_agent.id,
        frame=_progress_frame(command.id, wrong_scan, 1, machines=4),
        now=NOW,
    ) == "ok"
    command.status = "done"
    administrative_session.add(command)
    administrative_session.commit()
    assert apply_progress(
        administrative_session,
        agent_id=provisioned_agent.id,
        frame=_progress_frame(command.id, scan.scan_id, 2, machines=5),
        now=NOW,
    ) == "ok"

    administrative_session.refresh(scan)
    assert scan.progress_json is None


def test_apply_progress_ignores_terminal_scan_statuses(
    administrative_session: Session, seeded_org, provisioned_agent
) -> None:
    scan, command = _seed_scan_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )

    for status in ("completed", "failed", "cancelled"):
        scan.status = status
        administrative_session.add(scan)
        administrative_session.commit()
        assert apply_progress(
            administrative_session,
            agent_id=provisioned_agent.id,
            frame=_progress_frame(command.id, scan.scan_id, 1, machines=5),
            now=NOW,
        ) == "ok"

    administrative_session.refresh(scan)
    assert scan.progress_json is None
    assert scan.progress_seq == 0


def test_apply_progress_rejects_command_owned_by_another_agent(
    administrative_session: Session, seeded_org, provisioned_agent
) -> None:
    scan, command = _seed_scan_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )

    assert apply_progress(
        administrative_session,
        agent_id=uuid4(),
        frame=_progress_frame(command.id, scan.scan_id, 1, machines=5),
        now=NOW,
    ) == "unknown_command"

    administrative_session.refresh(scan)
    assert scan.progress_json is None
