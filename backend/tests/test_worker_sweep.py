from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import api.services.worker as worker_module
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import AIScanAnalysisRecord, ScanRecord
from sqlmodel import Session

NOW = datetime.now(UTC)
STALE = NOW - timedelta(hours=1)


def _seed_agent(
    session: Session, org_id, *, last_seen_at=None, connected_at=None
) -> Agent:
    agent = Agent(
        org_id=org_id,
        display_name=f"agent-{uuid4()}",
        public_key=b"\x01" * 32,
        last_seen_at=last_seen_at,
        connected_at=connected_at,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def _seed_scan(session: Session, org_id) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=NOW,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def _seed_command(
    session: Session,
    *,
    org_id,
    agent_id,
    status: str,
    scan_id=None,
) -> Command:
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
    session.refresh(command)
    return command


def test_run_worker_once_calls_global_sweep_before_enrichment(monkeypatch):
    session = object()
    sweep_calls: list[dict] = []
    enrichment_calls: list[tuple] = []

    def _fake_sweep(sess, *, now, grace_seconds=None, agent_id=None):
        sweep_calls.append(
            {
                "session": sess,
                "now": now,
                "grace_seconds": grace_seconds,
                "agent_id": agent_id,
            }
        )
        return 0

    def _fake_enrichment(sess, *, batch_size, client=None):
        enrichment_calls.append((sess, batch_size))
        return 4

    monkeypatch.setattr(worker_module, "get_session", lambda: iter([session]))
    monkeypatch.setattr(worker_module, "sweep_stale_commands", _fake_sweep)
    monkeypatch.setattr(
        worker_module, "process_pending_enrichment_jobs", _fake_enrichment
    )

    assert worker_module.run_worker_once(batch_size=9) == 4
    assert len(sweep_calls) == 1
    assert sweep_calls[0]["session"] is session
    assert sweep_calls[0]["agent_id"] is None
    assert sweep_calls[0]["now"].tzinfo is not None
    assert enrichment_calls == [(session, 9)]


def test_run_worker_once_ignores_pending_ai_jobs(
    monkeypatch, administrative_session, seeded_org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    scan.status = "completed"
    administrative_session.add(scan)
    ai_record = AIScanAnalysisRecord(
        scan_id=scan.scan_id,
        provider="groq",
        model="openai/gpt-oss-120b",
        status="pending",
        context_version="1",
        prompt_version="1",
    )
    administrative_session.add(ai_record)
    administrative_session.commit()

    enrichment_calls: list[tuple] = []

    def _fake_enrichment(session, *, batch_size, client=None):
        enrichment_calls.append((session, batch_size))
        return 2

    monkeypatch.setattr(
        worker_module, "get_session", lambda: iter([administrative_session])
    )
    monkeypatch.setattr(
        worker_module, "process_pending_enrichment_jobs", _fake_enrichment
    )

    assert worker_module.run_worker_once(batch_size=5) == 2
    assert enrichment_calls == [(administrative_session, 5)]

    administrative_session.refresh(ai_record)
    assert ai_record.status == "pending"


def test_run_worker_once_sweeps_stale_and_keeps_enrichment(
    monkeypatch, administrative_session: Session, seeded_org: Org
):
    stale_queued_agent = _seed_agent(
        administrative_session, seeded_org.id, last_seen_at=STALE
    )
    stale_delivered_agent = _seed_agent(
        administrative_session, seeded_org.id, last_seen_at=STALE
    )
    stale_running_agent = _seed_agent(
        administrative_session, seeded_org.id, last_seen_at=STALE
    )
    live_agent = _seed_agent(
        administrative_session,
        seeded_org.id,
        last_seen_at=STALE,
        connected_at=NOW,
    )

    queued = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=stale_queued_agent.id,
        status="queued",
    )
    delivered_scan = _seed_scan(administrative_session, seeded_org.id)
    delivered = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=stale_delivered_agent.id,
        status="delivered",
        scan_id=delivered_scan.scan_id,
    )
    running_scan = _seed_scan(administrative_session, seeded_org.id)
    running = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=stale_running_agent.id,
        status="running",
        scan_id=running_scan.scan_id,
    )
    live_scan = _seed_scan(administrative_session, seeded_org.id)
    live = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=live_agent.id,
        status="running",
        scan_id=live_scan.scan_id,
    )

    enrichment_calls: list[object] = []

    def _fake_enrichment(session, *, batch_size, client=None):
        enrichment_calls.append((session, batch_size))
        return 3

    monkeypatch.setattr(
        worker_module, "get_session", lambda: iter([administrative_session])
    )
    monkeypatch.setattr(
        worker_module, "process_pending_enrichment_jobs", _fake_enrichment
    )

    processed = worker_module.run_worker_once(batch_size=7)

    assert processed == 3
    assert enrichment_calls == [(administrative_session, 7)]

    administrative_session.refresh(queued)
    administrative_session.refresh(delivered)
    administrative_session.refresh(running)
    administrative_session.refresh(live)
    administrative_session.refresh(delivered_scan)
    administrative_session.refresh(running_scan)
    administrative_session.refresh(live_scan)

    assert queued.status == "expired"
    assert delivered.status == "failed"
    assert running.status == "failed"
    assert live.status == "running"
    assert delivered_scan.status == "failed"
    assert running_scan.status == "failed"
    assert live_scan.status == "pending"
