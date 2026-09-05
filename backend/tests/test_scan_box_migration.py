from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260904_18_scan_box_and_duration.py"
    spec = importlib.util.spec_from_file_location("scan_box_and_duration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260904_18"
    assert migration.down_revision == "20260811_17"


def test_migration_upgrade_creates_index(monkeypatch) -> None:
    migration = _load_migration()
    indexes: list[dict[str, object]] = []
    executed: list[object] = []

    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table_name, columns, **kwargs: indexes.append(
            {"name": name, "table": table_name, "columns": columns}
        ),
    )
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()

    assert indexes == [
        {
            "name": "ix_scans_org_id_agent_id",
            "table": "scans",
            "columns": ["org_id", "agent_id"],
        }
    ]
    assert len(executed) == 1


def test_backfill_copies_command_agent_and_leaves_orphans(
    administrative_session: Session,
) -> None:
    org = Org(name=f"org-{uuid4()}")
    administrative_session.add(org)
    administrative_session.commit()
    administrative_session.refresh(org)
    agent = Agent(
        org_id=org.id,
        display_name="box",
        public_key=b"\x01" * 32,
    )
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)
    now = datetime.now(timezone.utc)
    linked = ScanRecord(
        scan_id=uuid4(),
        org_id=org.id,
        timestamp=now,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="completed",
    )
    orphan = ScanRecord(
        scan_id=uuid4(),
        org_id=org.id,
        timestamp=now,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="completed",
    )
    administrative_session.add(linked)
    administrative_session.add(orphan)
    administrative_session.commit()
    command = Command(
        org_id=org.id,
        agent_id=agent.id,
        scan_id=linked.scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status="failed",
    )
    administrative_session.add(command)
    administrative_session.commit()

    migration = _load_migration()
    administrative_session.execute(migration.sa.text(
        """
        UPDATE scans AS s
        SET agent_id = c.agent_id
        FROM commands AS c
        WHERE s.scan_id = c.scan_id
          AND s.agent_id IS NULL
          AND c.agent_id IS NOT NULL
        """
    ))
    administrative_session.commit()

    administrative_session.refresh(linked)
    administrative_session.refresh(orphan)
    assert linked.agent_id == agent.id
    assert orphan.agent_id is None
