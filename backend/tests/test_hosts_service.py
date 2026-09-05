from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from api.dependencies.agent_auth import AgentIdentity
from api.models.activity import ActivityRecord
from api.models.command import Agent
from api.models.identity import Org
from api.schemas import HostPayload, ScanIngestRequest
from api.services.persistence import ingest_scan
from sqlmodel import Session, select


def _activity_rows(
    session: Session, org_id, kind: str | None = None
) -> list[ActivityRecord]:
    statement = select(ActivityRecord).where(ActivityRecord.org_id == org_id)
    if kind is not None:
        statement = statement.where(ActivityRecord.kind == kind)
    return list(session.exec(statement).all())


def _scan(
    scan_id, *, hosts: list[HostPayload], timestamp: datetime | None = None
) -> ScanIngestRequest:
    return ScanIngestRequest(
        scan_id=scan_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=hosts,
        findings=[],
    )


def test_later_ingest_new_host_writes_one_machine_first_seen(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    first_at = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    later_at = first_at + timedelta(hours=1)
    first_host = HostPayload(
        ip="10.0.0.1",
        mac="AA:BB:CC:DD:EE:01",
        hostname="known-host",
        vendor="vendor",
        ports=[],
    )
    ingest_scan(
        runtime_session,
        _scan(uuid4(), hosts=[first_host], timestamp=first_at),
        identity=identity,
        now=later_at,
    )

    new_host = HostPayload(
        ip="10.0.0.2",
        mac="AA:BB:CC:DD:EE:02",
        hostname="new-host",
        vendor="vendor",
        ports=[],
    )
    ingest_scan(
        runtime_session,
        _scan(uuid4(), hosts=[first_host, new_host], timestamp=later_at),
        identity=identity,
        now=later_at,
    )

    seen = _activity_rows(
        runtime_session, seeded_org.id, kind="machine_first_seen"
    )
    assert len(seen) == 1
    assert seen[0].payload == {"hostname": "new-host"}


def test_later_ingest_known_host_writes_no_machine_first_seen(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    first_at = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    later_at = first_at + timedelta(hours=1)
    host = HostPayload(
        ip="10.0.0.3",
        mac="AA:BB:CC:DD:EE:03",
        hostname="repeat-host",
        vendor="vendor",
        ports=[],
    )
    ingest_scan(
        runtime_session,
        _scan(uuid4(), hosts=[host], timestamp=first_at),
        identity=identity,
        now=later_at,
    )
    ingest_scan(
        runtime_session,
        _scan(uuid4(), hosts=[host], timestamp=later_at),
        identity=identity,
        now=later_at,
    )

    assert _activity_rows(
        runtime_session, seeded_org.id, kind="machine_first_seen"
    ) == []
