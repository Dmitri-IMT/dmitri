from __future__ import annotations

import tomllib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from api.management import import_scan
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import FindingRecord, ScanHostRecord, ScanRecord
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = (
    ROOT.parent / "contracts" / "examples" / "scan_result.example.json"
)


def test_import_scan_persists_valid_payload(
    migrated_database,
    administrative_session: Session,
    provisioned_agent: Agent,
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = import_scan.main(
        ["--file", str(EXAMPLE_PATH), "--agent-id", str(provisioned_agent.id)]
    )

    assert exit_code == 0
    scan = administrative_session.exec(select(ScanRecord)).one()
    assert scan.agent_id == provisioned_agent.id
    assert len(administrative_session.exec(select(ScanHostRecord)).all()) == 2
    assert len(administrative_session.exec(select(FindingRecord)).all()) == 2
    output = capsys.readouterr().out
    assert "status=imported" in output
    assert f"scan_id={scan.scan_id}" in output
    assert "hosts_received=2" in output
    assert "findings_received=2" in output


def test_import_scan_is_idempotent(
    migrated_database,
    administrative_session: Session,
    provisioned_agent: Agent,
) -> None:
    args = ["--file", str(EXAMPLE_PATH), "--agent-id", str(provisioned_agent.id)]

    assert import_scan.main(args) == 0
    assert import_scan.main(args) == 0

    assert len(administrative_session.exec(select(ScanRecord)).all()) == 1
    assert len(administrative_session.exec(select(ScanHostRecord)).all()) == 2
    assert len(administrative_session.exec(select(FindingRecord)).all()) == 2


def test_import_scan_creates_and_reuses_org_import_agent(
    migrated_database,
    administrative_session: Session,
    seeded_org: Org,
    capsys: pytest.CaptureFixture,
) -> None:
    args = ["--file", str(EXAMPLE_PATH), "--org-id", str(seeded_org.id)]

    assert import_scan.main(args) == 0
    first_output = capsys.readouterr().out
    assert import_scan.main(args) == 0
    second_output = capsys.readouterr().out

    agents = administrative_session.exec(
        select(Agent).where(Agent.display_name == import_scan.IMPORT_AGENT_NAME)
    ).all()
    assert len(agents) == 1
    assert f"agent_id={agents[0].id}" in first_output
    assert f"agent_id={agents[0].id}" in second_output
    assert "private_key" not in first_output
    assert "private_key" not in second_output


def test_import_scan_rejects_unknown_agent(
    migrated_database,
    administrative_session: Session,
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = import_scan.main(
        ["--file", str(EXAMPLE_PATH), "--agent-id", str(uuid4())]
    )

    assert exit_code == 1
    assert "unknown agent" in capsys.readouterr().err
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_import_scan_rejects_unknown_organization(
    migrated_database,
    administrative_session: Session,
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = import_scan.main(
        ["--file", str(EXAMPLE_PATH), "--org-id", str(uuid4())]
    )

    assert exit_code == 1
    assert "unknown organization" in capsys.readouterr().err
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_import_scan_rejects_revoked_agent(
    migrated_database,
    administrative_session: Session,
    provisioned_agent: Agent,
    capsys: pytest.CaptureFixture,
) -> None:
    provisioned_agent.revoked_at = datetime.now(timezone.utc)
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    exit_code = import_scan.main(
        ["--file", str(EXAMPLE_PATH), "--agent-id", str(provisioned_agent.id)]
    )

    assert exit_code == 1
    assert "agent is revoked" in capsys.readouterr().err
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_import_scan_rejects_invalid_payload_before_database_write(
    migrated_database,
    administrative_session: Session,
    provisioned_agent: Agent,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    invalid = tmp_path / "scan.json"
    invalid.write_text('{"scan_id":"not-a-uuid"}', encoding="utf-8")

    exit_code = import_scan.main(
        ["--file", str(invalid), "--agent-id", str(provisioned_agent.id)]
    )

    assert exit_code == 1
    assert "does not match ScanIngestRequest" in capsys.readouterr().err
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_import_scan_console_script_is_registered() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert (
        project["project"]["scripts"]["backend-import-scan"]
        == "api.management.import_scan:main"
    )
