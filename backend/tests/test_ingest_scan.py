from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from api.dependencies.agent_auth import AgentIdentity
from api.models.activity import ActivityRecord
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import (
    CPERecord,
    EnrichmentJobRecord,
    EpssCacheRecord,
    EpssRecord,
    FindingRecord,
    HostRecord,
    KevCacheRecord,
    KevRecord,
    PortRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas import HostPayload, PortPayload, ScanIngestRequest
from api.services import commands as commands_module
from api.services import persistence as persistence_module
from api.services import worker
from api.services.epss import EpssClient
from api.services.kev import KevClient
from api.services.nvd import NvdClient
from api.services.persistence import (
    ScanClosedError,
    ScanOwnershipError,
    _persist_scan_host,
    ingest_scan,
    persist_scan,
)
from sqlalchemy import JSON, text
from sqlmodel import Session, select

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "examples"
    / "scan_result.example.json"
)


def _activity_rows(
    session: Session, org_id, kind: str | None = None
) -> list[ActivityRecord]:
    statement = select(ActivityRecord).where(ActivityRecord.org_id == org_id)
    if kind is not None:
        statement = statement.where(ActivityRecord.kind == kind)
    return list(session.exec(statement).all())


def _example_scan() -> tuple[dict[str, object], ScanIngestRequest]:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    return payload, ScanIngestRequest.model_validate(payload)


def _seed_org(session: Session) -> Org:
    org = Org(name=f"org-{uuid4()}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _seed_agent(session: Session, org_id) -> Agent:
    agent = Agent(
        org_id=org_id, display_name=f"agent-{uuid4()}", public_key=b"\x01" * 32
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def _seed_placeholder(
    session: Session, *, org_id, agent_id, scan_id, now: datetime
) -> Command:
    scan_record = ScanRecord(
        scan_id=scan_id,
        org_id=org_id,
        timestamp=now,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    session.add(scan_record)
    session.commit()
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status="delivered",
        delivered_at=now,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def _scan(scan_id, *, hosts: list[HostPayload] | None = None) -> ScanIngestRequest:
    return ScanIngestRequest(
        scan_id=scan_id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=hosts or [],
        findings=[],
    )


def _fake_nvd_payload(cve_id: str) -> dict[str, object]:
    return {
        "vulnerabilities": [
            {
                "cve": {
                    "id": cve_id,
                    "descriptions": [
                        {"lang": "en", "value": f"NVD description for {cve_id}."}
                    ],
                    "references": [
                        {"url": f"https://nvd.nist.gov/vuln/detail/{cve_id}"}
                    ],
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 8.1}}]},
                }
            }
        ]
    }


def _fake_kev_payload(cve_id: str) -> dict[str, object]:
    return {
        "cve_id": cve_id,
        "date_added": datetime(2026, 5, 12, tzinfo=timezone.utc),
        "known_ransomware": True,
        "required_action": "Patch immediately.",
        "raw_json": {
            "cveID": cve_id,
            "knownRansomwareCampaignUse": "Known",
            "requiredAction": "Patch immediately.",
        },
    }


def _fake_epss_payload(cve_id: str) -> dict[str, object]:
    return {
        "cve_id": cve_id,
        "epss_score": 0.91,
        "percentile": 0.98,
        "scored_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
        "raw_json": {
            "cve": cve_id,
            "epss": "0.91",
            "percentile": "0.98",
        },
    }


def test_ingest_scan_accepts_enriched_findings_example(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    payload, scan = _example_scan()

    record = persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )
    scan_hosts = runtime_session.exec(select(ScanHostRecord)).all()

    assert len(scan_hosts) == len(payload["hosts"])
    assert str(record.scan_id) == payload["scan_id"]
    assert record.scan_mode == scan.scan_mode
    assert record.status == "completed"
    assert record.agent_id == provisioned_agent.id


def test_scan_hosts_persist_exact_operating_system_snapshots(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    payload, scan = _example_scan()

    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )

    scan_hosts = runtime_session.exec(
        select(ScanHostRecord).order_by(ScanHostRecord.ip)
    ).all()
    assert scan_hosts[0].operating_system_json == payload["hosts"][0][
        "operating_system"
    ]
    assert scan_hosts[1].operating_system_json is None

    scan_host_is_sql_null = runtime_session.execute(
        text(
            "SELECT operating_system_json IS NULL FROM scan_hosts WHERE ip = :ip"
        ),
        {"ip": "192.168.1.40"},
    ).scalar_one()
    inventory_host_is_sql_null = runtime_session.execute(
        text("SELECT operating_system_json IS NULL FROM hosts WHERE ip = :ip"),
        {"ip": "192.168.1.40"},
    ).scalar_one()
    assert scan_host_is_sql_null is True
    assert inventory_host_is_sql_null is True


def test_scan_host_snapshot_omits_null_operating_system_details() -> None:
    operating_system = {
        "name": "Linux 5",
        "accuracy": 91,
        "vendor": None,
        "family": None,
        "generation": None,
        "device_type": None,
        "cpes": [],
    }
    host = HostPayload(
        ip="192.168.1.10",
        mac=None,
        hostname="host",
        vendor="vendor",
        operating_system=operating_system,
        ports=[],
    )

    class RecordingSession:
        def add(self, _record) -> None:
            pass

        def flush(self) -> None:
            pass

    record = _persist_scan_host(RecordingSession(), uuid4(), host)  # type: ignore[arg-type]

    assert record.operating_system_json == {
        "name": "Linux 5",
        "accuracy": 91,
        "cpes": [],
    }


@pytest.mark.parametrize("record_type", (ScanHostRecord, HostRecord))
def test_operating_system_columns_store_python_none_as_sql_null(record_type) -> None:
    column = record_type.__table__.c.operating_system_json

    assert isinstance(column.type, JSON)
    assert column.type.none_as_null is True


def test_worker_processes_pending_jobs_separately(
    monkeypatch, runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:  # type: ignore[no-untyped-def]
    _, scan = _example_scan()
    monkeypatch.setattr(
        NvdClient,
        "query_by_cpe",
        lambda self, session, cpe: _fake_nvd_payload("CVE-2016-10012"),
    )
    monkeypatch.setattr(
        NvdClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_nvd_payload(cve_id),
    )
    monkeypatch.setattr(
        KevClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_kev_payload(cve_id),
    )
    monkeypatch.setattr(
        EpssClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_epss_payload(cve_id),
    )

    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )
    jobs_before = runtime_session.exec(select(EnrichmentJobRecord)).all()
    findings_before = runtime_session.exec(select(FindingRecord)).all()
    assert jobs_before
    assert all(job.status == "pending" for job in jobs_before)
    assert all(finding.confidence != "confirmed" for finding in findings_before)

    monkeypatch.setattr(worker, "get_session", lambda: iter([runtime_session]))
    processed = worker.run_worker_once(batch_size=25)
    assert processed == len(jobs_before)

    jobs_after = runtime_session.exec(select(EnrichmentJobRecord)).all()
    findings_after = runtime_session.exec(select(FindingRecord)).all()
    kev_records = runtime_session.exec(select(KevRecord)).all()
    epss_records = runtime_session.exec(select(EpssRecord)).all()
    risk_snapshots = runtime_session.exec(select(RiskSnapshotRecord)).all()
    assert all(job.status == "completed" for job in jobs_after)
    assert all(job.attempts == 1 for job in jobs_after)
    assert any(finding.confidence == "confirmed" for finding in findings_after)
    assert any("nvd" in finding.source_labels_json for finding in findings_after)
    assert any("kev" in finding.source_labels_json for finding in findings_after)
    assert any("epss" in finding.source_labels_json for finding in findings_after)
    assert kev_records
    assert epss_records
    assert risk_snapshots
    assert any(snapshot.risk_score > 0 for snapshot in risk_snapshots)


def test_worker_marks_job_failed_when_processing_raises(
    monkeypatch, runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:  # type: ignore[no-untyped-def]
    _, scan = _example_scan()
    monkeypatch.setattr(
        NvdClient,
        "query_by_cpe",
        lambda self, session, cpe: _fake_nvd_payload("CVE-2016-10012"),
    )
    monkeypatch.setattr(
        NvdClient,
        "query_by_cve",
        lambda self, session, cve_id: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        KevClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_kev_payload(cve_id),
    )
    monkeypatch.setattr(
        EpssClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_epss_payload(cve_id),
    )

    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )
    monkeypatch.setattr(worker, "get_session", lambda: iter([runtime_session]))
    processed = worker.run_worker_once(batch_size=1)
    assert processed == 1

    jobs = runtime_session.exec(
        select(EnrichmentJobRecord).order_by(EnrichmentJobRecord.id)
    ).all()
    assert jobs[0].status == "failed"
    assert jobs[0].last_error == "boom"
    assert jobs[0].attempts == 1
    assert jobs[0].completed_at is not None


def test_kev_and_epss_cache_store_json_safe_dates(
    monkeypatch, runtime_session: Session
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        KevClient,
        "_fetch_from_remote",
        lambda self, cve_id: _fake_kev_payload(cve_id),
    )
    monkeypatch.setattr(
        EpssClient,
        "_fetch_from_remote",
        lambda self, cve_id: _fake_epss_payload(cve_id),
    )

    kev_payload = KevClient().query_by_cve(runtime_session, "CVE-2016-10012")
    epss_payload = EpssClient().query_by_cve(runtime_session, "CVE-2016-10012")
    kev_cache = runtime_session.get(KevCacheRecord, "CVE-2016-10012")
    epss_cache = runtime_session.get(EpssCacheRecord, "CVE-2016-10012")

    assert kev_payload is not None
    assert epss_payload is not None
    assert kev_cache is not None
    assert epss_cache is not None
    assert kev_cache.response_json["date_added"] == "2026-05-12"
    assert epss_cache.response_json["scored_at"] == "2026-05-12"


def test_ingest_scan_cpe_produces_one_nvd_cpe_job_per_distinct_cpe(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    host_a = HostPayload(
        ip="10.0.0.5",
        mac=None,
        hostname="host-a",
        vendor="vendor",
        ports=[
            PortPayload(
                port=443,
                protocol="tcp",
                state="open",
                service="https",
                cpes=["cpe:2.3:a:x:y:1:*", "cpe:2.3:a:x:y:1:*", "cpe:2.3:a:x:z:2:*"],
            )
        ],
    )
    host_b = HostPayload(
        ip="10.0.0.6",
        mac=None,
        hostname="host-b",
        vendor="vendor",
        ports=[
            PortPayload(
                port=8443,
                protocol="tcp",
                state="open",
                service="https",
                cpes=["cpe:2.3:a:x:y:1:*"],
            )
        ],
    )
    scan_id = uuid4()
    scan = _scan(scan_id, hosts=[host_a, host_b])
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)

    def _cpe_jobs() -> list[EnrichmentJobRecord]:
        return runtime_session.exec(
            select(EnrichmentJobRecord).where(
                EnrichmentJobRecord.scan_id == scan_id,
                EnrichmentJobRecord.job_type == "nvd_cpe",
            )
        ).all()

    ingest_scan(
        runtime_session, scan, identity=identity, now=datetime.now(timezone.utc)
    )
    jobs = _cpe_jobs()
    assert sorted(job.target_value for job in jobs) == [
        "cpe:2.3:a:x:y:1:*",
        "cpe:2.3:a:x:y:1:*",
        "cpe:2.3:a:x:z:2:*",
    ]
    assert len(jobs) == 3
    port_ids = {job.port_id for job in jobs}
    assert len(port_ids) == 2

    ingest_scan(
        runtime_session, scan, identity=identity, now=datetime.now(timezone.utc)
    )
    assert len(_cpe_jobs()) == 3


def test_ingest_scan_preserves_first_seen_across_calls(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    mac = "AA:BB:CC:DD:EE:FF"
    host = HostPayload(
        ip="10.0.0.9", mac=mac, hostname="host", vendor="vendor", ports=[]
    )
    first_scan = _scan(uuid4(), hosts=[host])
    second_scan = _scan(uuid4(), hosts=[host])

    ingest_scan(
        runtime_session, first_scan, identity=identity, now=datetime.now(timezone.utc)
    )
    first_host = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == first_scan.scan_id)
    ).one()
    ingest_scan(
        runtime_session, second_scan, identity=identity, now=datetime.now(timezone.utc)
    )

    assert first_host.host_id is not None
    second_host = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == second_scan.scan_id)
    ).one()
    assert second_host.host_id == first_host.host_id


def _scan_with_findable_payload(scan_id) -> ScanIngestRequest:
    host = HostPayload(
        ip="10.0.0.99",
        mac=None,
        hostname="host",
        vendor="vendor",
        ports=[
            PortPayload(
                port=22,
                protocol="tcp",
                state="open",
                service="ssh",
                cpes=["cpe:2.3:a:x:y:1:*"],
            )
        ],
    )
    return _scan(scan_id, hosts=[host])


def test_ingest_scan_rejects_placeholder_owned_by_another_agent(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    other_agent = _seed_agent(runtime_session, seeded_org.id)
    scan_id = uuid4()
    now = datetime.now(timezone.utc)
    command = _seed_placeholder(
        runtime_session,
        org_id=seeded_org.id,
        agent_id=other_agent.id,
        scan_id=scan_id,
        now=now,
    )
    scan = _scan_with_findable_payload(scan_id)
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)

    with pytest.raises(ScanOwnershipError):
        ingest_scan(runtime_session, scan, identity=identity, now=now)

    runtime_session.refresh(command)
    assert command.status == "delivered"
    placeholder = runtime_session.get(ScanRecord, scan_id)
    assert placeholder.status == "pending"
    assert (
        runtime_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )
    assert runtime_session.exec(select(PortRecord)).first() is None
    assert (
        runtime_session.exec(
            select(EnrichmentJobRecord).where(EnrichmentJobRecord.scan_id == scan_id)
        ).first()
        is None
    )


def test_persist_scan_refuses_stub_agent_mismatch(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    other_agent = _seed_agent(runtime_session, seeded_org.id)
    scan_id = uuid4()
    now = datetime.now(timezone.utc)
    _seed_placeholder(
        runtime_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    stub = runtime_session.get(ScanRecord, scan_id)
    stub.agent_id = other_agent.id
    runtime_session.add(stub)
    runtime_session.commit()
    scan = _scan_with_findable_payload(scan_id)
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)

    with pytest.raises(ScanOwnershipError):
        ingest_scan(runtime_session, scan, identity=identity, now=now)

    runtime_session.refresh(stub)
    assert stub.agent_id == other_agent.id
    assert stub.status == "pending"
    assert (
        runtime_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )


def test_ingest_scan_rejects_placeholder_from_another_org(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    other_org = _seed_org(runtime_session)
    other_agent = _seed_agent(runtime_session, other_org.id)
    scan_id = uuid4()
    now = datetime.now(timezone.utc)
    command = _seed_placeholder(
        runtime_session,
        org_id=other_org.id,
        agent_id=other_agent.id,
        scan_id=scan_id,
        now=now,
    )
    scan = _scan_with_findable_payload(scan_id)
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)

    with pytest.raises(ScanOwnershipError):
        ingest_scan(runtime_session, scan, identity=identity, now=now)

    runtime_session.refresh(command)
    assert command.status == "delivered"
    placeholder = runtime_session.get(ScanRecord, scan_id)
    assert placeholder.status == "pending"
    assert placeholder.org_id == other_org.id
    assert (
        runtime_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )


def test_ingest_scan_rejects_terminal_command(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    scan_id = uuid4()
    now = datetime.now(timezone.utc)
    command = _seed_placeholder(
        runtime_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    command.status = "failed"
    command.error_code = "device_offline"
    command.completed_at = now
    runtime_session.add(command)
    runtime_session.commit()

    scan = _scan_with_findable_payload(scan_id)
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)

    with pytest.raises(ScanClosedError):
        ingest_scan(runtime_session, scan, identity=identity, now=now)

    runtime_session.refresh(command)
    assert command.status == "failed"
    assert command.error_code == "device_offline"
    placeholder = runtime_session.get(ScanRecord, scan_id)
    assert placeholder.status == "pending"
    assert (
        runtime_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )
    assert runtime_session.exec(select(PortRecord)).first() is None
    assert (
        runtime_session.exec(
            select(EnrichmentJobRecord).where(EnrichmentJobRecord.scan_id == scan_id)
        ).first()
        is None
    )


def test_ingest_scan_repeated_submission_is_idempotent(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    _, scan = _example_scan()

    def _table_counts() -> dict[str, int]:
        return {
            "hosts": len(runtime_session.exec(select(ScanHostRecord)).all()),
            "ports": len(runtime_session.exec(select(PortRecord)).all()),
            "services": len(runtime_session.exec(select(ServiceRecord)).all()),
            "cpes": len(runtime_session.exec(select(CPERecord)).all()),
            "findings": len(runtime_session.exec(select(FindingRecord)).all()),
            "jobs": len(runtime_session.exec(select(EnrichmentJobRecord)).all()),
        }

    first = ingest_scan(
        runtime_session, scan, identity=identity, now=datetime.now(timezone.utc)
    )
    counts_after_first = _table_counts()
    assert counts_after_first["hosts"] == 3
    assert counts_after_first["ports"] == 5
    assert counts_after_first["services"] == 5
    assert counts_after_first["findings"] == 2
    assert counts_after_first["jobs"] > 0

    second = ingest_scan(
        runtime_session, scan, identity=identity, now=datetime.now(timezone.utc)
    )
    counts_after_second = _table_counts()

    assert second.scan_id == first.scan_id
    assert counts_after_second == counts_after_first


def test_ingest_scan_rejects_completed_scan_owned_by_another_agent(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    other_agent = _seed_agent(runtime_session, seeded_org.id)
    other_identity = AgentIdentity(agent_id=other_agent.id, org_id=seeded_org.id)
    scan = _scan_with_findable_payload(uuid4())
    ingest_scan(
        runtime_session, scan, identity=other_identity, now=datetime.now(timezone.utc)
    )
    hosts_before = runtime_session.exec(select(ScanHostRecord)).all()

    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    with pytest.raises(ScanOwnershipError):
        ingest_scan(
            runtime_session, scan, identity=identity, now=datetime.now(timezone.utc)
        )

    scan_record = runtime_session.get(ScanRecord, scan.scan_id)
    assert scan_record.agent_id == other_agent.id
    hosts_after = runtime_session.exec(select(ScanHostRecord)).all()
    assert len(hosts_after) == len(hosts_before)


def test_persist_scan_case_c_rolls_back_completely_when_apply_status_fails(
    migrated_database, seeded_org: Org, provisioned_agent: Agent
) -> None:
    scan_id = uuid4()
    now = datetime.now(timezone.utc)
    host = HostPayload(
        ip="10.0.0.30",
        mac=None,
        hostname="host",
        vendor="vendor",
        ports=[
            PortPayload(
                port=22,
                protocol="tcp",
                state="open",
                service="ssh",
                cpes=["cpe:2.3:a:x:y:1:*"],
            )
        ],
    )
    scan = _scan(scan_id, hosts=[host])

    with Session(migrated_database) as session:
        command = _seed_placeholder(
            session,
            org_id=seeded_org.id,
            agent_id=provisioned_agent.id,
            scan_id=scan_id,
            now=now,
        )
        command.status = "done"
        command.completed_at = now
        session.add(command)
        session.commit()
        session.refresh(command)
        command_id = command.id

        with pytest.raises(RuntimeError):
            persist_scan(
                session,
                scan,
                org_id=seeded_org.id,
                agent_id=provisioned_agent.id,
                command=command,
                now=now,
                existing=session.get(ScanRecord, scan_id),
            )

    with Session(migrated_database) as fresh_session:
        placeholder = fresh_session.get(ScanRecord, scan_id)
        assert placeholder.status == "pending"
        fresh_command = fresh_session.get(Command, command_id)
        assert fresh_command.status == "done"
        assert (
            fresh_session.exec(
                select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
            ).first()
            is None
        )
        assert fresh_session.exec(select(PortRecord)).first() is None
        assert fresh_session.exec(select(ServiceRecord)).first() is None
        assert fresh_session.exec(select(CPERecord)).first() is None
        assert (
            fresh_session.exec(
                select(FindingRecord).where(FindingRecord.scan_id == scan_id)
            ).first()
            is None
        )
        assert (
            fresh_session.exec(
                select(EnrichmentJobRecord).where(
                    EnrichmentJobRecord.scan_id == scan_id
                )
            ).first()
            is None
        )


def test_ingest_scan_case_a_rolls_back_completely_on_mid_ingest_failure(
    monkeypatch, migrated_database, seeded_org: Org, provisioned_agent: Agent
) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(persistence_module, "_enqueue_enrichment_jobs", _boom)

    scan_id = uuid4()
    host = HostPayload(
        ip="10.0.0.40",
        mac=None,
        hostname="host",
        vendor="vendor",
        ports=[
            PortPayload(
                port=22,
                protocol="tcp",
                state="open",
                service="ssh",
                cpes=["cpe:2.3:a:x:y:1:*"],
            )
        ],
    )
    scan = _scan(scan_id, hosts=[host])
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)

    with pytest.raises(RuntimeError):
        with Session(migrated_database) as failing_session:
            persistence_module.ingest_scan(
                failing_session,
                scan,
                identity=identity,
                now=datetime.now(timezone.utc),
            )

    with Session(migrated_database) as fresh_session:
        assert fresh_session.get(ScanRecord, scan_id) is None
        assert (
            fresh_session.exec(
                select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
            ).first()
            is None
        )
        assert fresh_session.exec(select(PortRecord)).first() is None
        assert fresh_session.exec(select(ServiceRecord)).first() is None
        assert fresh_session.exec(select(CPERecord)).first() is None
        assert (
            fresh_session.exec(
                select(EnrichmentJobRecord).where(
                    EnrichmentJobRecord.scan_id == scan_id
                )
            ).first()
            is None
        )


def test_persist_scan_writes_scan_finished(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    _, scan = _example_scan()
    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )

    finished = _activity_rows(
        runtime_session, seeded_org.id, kind="scan_finished"
    )
    assert len(finished) == 1
    assert finished[0].subject_id == scan.scan_id
    assert finished[0].actor_user_id is None
    assert finished[0].payload == {"scan_mode": scan.scan_mode}


def test_first_completed_ingest_writes_no_machine_first_seen(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    _, scan = _example_scan()
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    ingest_scan(
        runtime_session, scan, identity=identity, now=datetime.now(timezone.utc)
    )

    assert len(_activity_rows(runtime_session, seeded_org.id, "scan_finished")) == 1
    assert _activity_rows(runtime_session, seeded_org.id, "machine_first_seen") == []


def test_clock_skew_finished_sorts_above_started(
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
) -> None:
    # Both writers stamp `occurred_at` from the API clock handed to them as
    # `now`, so the box's own timestamp cannot leak into the activity order.
    started_at = datetime(2026, 6, 2, 6, 0, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 6, 2, 6, 12, 0, tzinfo=timezone.utc)
    box_timestamp = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

    command = Command(
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status="queued",
    )
    administrative_session.add(command)
    administrative_session.commit()
    administrative_session.refresh(command)

    scan_id = uuid4()
    commands_module._record_delivery(
        administrative_session,
        command=command,
        scan_id=scan_id,
        now=started_at,
    )

    host = HostPayload(
        ip="10.0.0.50",
        mac="AA:BB:CC:DD:EE:01",
        hostname="skew-host",
        vendor="vendor",
        ports=[],
    )
    scan = ScanIngestRequest(
        scan_id=scan_id,
        timestamp=box_timestamp,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=[host],
        findings=[],
    )
    command = administrative_session.exec(
        select(Command).where(Command.scan_id == scan_id)
    ).one()
    persist_scan(
        administrative_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=command,
        now=finished_at,
        existing=administrative_session.get(ScanRecord, scan_id),
    )

    rows = list(
        administrative_session.exec(
            select(ActivityRecord)
            .where(ActivityRecord.org_id == seeded_org.id)
            .order_by(ActivityRecord.occurred_at.desc(), ActivityRecord.id.desc())
        ).all()
    )
    kinds = [row.kind for row in rows]
    assert kinds.index("scan_finished") < kinds.index("scan_started")
    assert rows[0].kind == "scan_finished"
    assert rows[0].occurred_at == finished_at
    assert rows[1].occurred_at == started_at
