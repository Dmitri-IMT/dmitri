from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity
from api.main import app
from api.models.activity import ActivityRecord
from api.models.command import Agent, Command
from api.models.identity import Org, User
from api.models.persistence import (
    AIChatMessageRecord,
    AIScanAnalysisRecord,
    AIUsageRecord,
    FindingRecord,
    HostRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.schemas import HostPayload, ScanIngestRequest
from api.schemas.scan import FindingPayload, PortPayload
from api.services.persistence import ScanClosedError, ingest_scan
from fastapi.testclient import TestClient
from sqlmodel import Session, select

Headers = Callable[[UUID, str], dict[str, str]]
T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(runtime_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_session() -> Generator[Session, None, None]:
        yield runtime_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def identity(seeded_org: Org, provisioned_agent: Agent) -> AgentIdentity:
    return AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)


def _host(ip: str, mac: str, hostname: str) -> HostPayload:
    return HostPayload(
        ip=ip,
        mac=mac,
        hostname=hostname,
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


HOST_A = _host("10.0.0.1", "AA:00:00:00:00:01", "a")


def _finding(ip: str) -> FindingPayload:
    return FindingPayload(
        ip=ip,
        port=22,
        protocol="tcp",
        service="ssh",
        severity="high",
        title="Weak SSH",
        description="Weak SSH config",
        recommendation="Harden SSH",
        evidence="banner",
    )


def _ingest(
    session: Session,
    identity: AgentIdentity,
    hosts: list[HostPayload],
    *,
    at: datetime = T0,
    scan_id: UUID | None = None,
) -> UUID:
    scan_id = scan_id or uuid4()
    ingest_scan(
        session,
        ScanIngestRequest(
            scan_id=scan_id,
            timestamp=at,
            subnet="10.0.0.0/24",
            scan_mode="standard",
            hosts=hosts,
            findings=[_finding(str(host.ip)) for host in hosts],
        ),
        identity=identity,
        now=at,
    )
    return scan_id


def _running_scan(session: Session, org_id: UUID) -> UUID:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=T0,
        subnet="10.0.0.0/24",
        scan_mode="standard",
        status="processing",
    )
    session.add(scan)
    session.commit()
    return scan.scan_id


def _activity(session: Session, org_id: UUID, kind: str) -> list[ActivityRecord]:
    session.expire_all()
    return list(
        session.exec(
            select(ActivityRecord).where(
                ActivityRecord.org_id == org_id, ActivityRecord.kind == kind
            )
        ).all()
    )


def _host_id(session: Session, org_id: UUID, ip: str) -> UUID:
    session.expire_all()
    return session.exec(
        select(HostRecord.id).where(HostRecord.org_id == org_id, HostRecord.ip == ip)
    ).one()


def test_admin_deletes_finished_scan_with_its_ai_data(
    client: TestClient,
    runtime_session: Session,
    administrative_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    headers = actor_headers(seeded_org.id, "admin")
    scan_id = _ingest(runtime_session, identity, [HOST_A])
    user = administrative_session.exec(select(User)).first()
    assert user is not None
    administrative_session.add(
        AIScanAnalysisRecord(
            scan_id=scan_id,
            provider="groq",
            model="m",
            language="pt",
            context_version="1",
            prompt_version="1",
        )
    )
    administrative_session.add(
        AIChatMessageRecord(
            scan_id=scan_id, user_id=user.id, scope_id=scan_id, question="q", answer="a"
        )
    )
    administrative_session.add(
        AIUsageRecord(
            org_id=seeded_org.id,
            scan_id=scan_id,
            operation="chat",
            provider="groq",
            model="m",
            status="ok",
        )
    )
    administrative_session.commit()

    response = client.delete(f"/api/v1/scans/{scan_id}", headers=headers)

    assert response.status_code == 204
    runtime_session.expire_all()
    assert runtime_session.get(ScanRecord, scan_id) is None
    assert runtime_session.exec(
        select(AIScanAnalysisRecord).where(AIScanAnalysisRecord.scan_id == scan_id)
    ).all() == []
    assert runtime_session.exec(
        select(AIChatMessageRecord).where(AIChatMessageRecord.scan_id == scan_id)
    ).all() == []
    usage = runtime_session.exec(select(AIUsageRecord)).one()
    assert usage.scan_id is None
    listed = client.get("/api/v1/scans", headers=headers).json()["data"]
    assert scan_id not in {UUID(row["scan_id"]) for row in listed}
    assert runtime_session.exec(select(HostRecord)).all() == []
    [entry] = _activity(runtime_session, seeded_org.id, "scans_deleted")
    assert entry.subject_id == scan_id
    assert entry.payload["count"] == "1"
    assert entry.payload["machines_removed"] == "1"


def test_scan_started_by_a_pi_command_is_deleted_with_its_command(
    client: TestClient,
    runtime_session: Session,
    administrative_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    scan_id = _ingest(runtime_session, identity, [HOST_A])
    command = Command(
        org_id=seeded_org.id,
        agent_id=identity.agent_id,
        scan_id=scan_id,
        scan_mode="standard",
        subnet="10.0.0.0/24",
        status="done",
    )
    command_id = command.id
    administrative_session.add(command)
    administrative_session.commit()

    response = client.delete(
        f"/api/v1/scans/{scan_id}", headers=actor_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 204
    runtime_session.expire_all()
    assert runtime_session.get(ScanRecord, scan_id) is None
    assert runtime_session.get(Command, command_id) is None


def test_deleted_scan_upload_is_refused(
    client: TestClient,
    runtime_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    scan_id = _ingest(runtime_session, identity, [HOST_A])
    headers = actor_headers(seeded_org.id, "admin")
    client.delete(f"/api/v1/scans/{scan_id}", headers=headers)

    with pytest.raises(ScanClosedError):
        _ingest(runtime_session, identity, [HOST_A], scan_id=scan_id)


def test_running_scan_delete_is_refused(
    client: TestClient,
    runtime_session: Session,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    scan_id = _running_scan(runtime_session, seeded_org.id)

    response = client.delete(
        f"/api/v1/scans/{scan_id}", headers=actor_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "scan_running"
    runtime_session.expire_all()
    assert runtime_session.get(ScanRecord, scan_id) is not None
    assert _activity(runtime_session, seeded_org.id, "scans_deleted") == []


def test_delete_all_scans_skips_running_scans(
    client: TestClient,
    runtime_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    for minutes in range(3):
        _ingest(
            runtime_session, identity, [HOST_A], at=T0 + timedelta(minutes=minutes)
        )
    running = _running_scan(runtime_session, seeded_org.id)
    headers = actor_headers(seeded_org.id, "admin")

    response = client.delete("/api/v1/scans", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"deleted": 3, "skipped": 1, "machines_removed": 1}
    runtime_session.expire_all()
    assert runtime_session.exec(select(ScanRecord.scan_id)).all() == [running]
    [entry] = _activity(runtime_session, seeded_org.id, "scans_deleted")
    assert entry.subject_id is None
    assert entry.payload["skipped"] == "1"


def test_deleting_newest_scan_rebuilds_machine_from_remaining_scan(
    client: TestClient,
    runtime_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    _ingest(runtime_session, identity, [_host("10.0.0.1", "AA:00:00:00:00:01", "old")])
    newest = _ingest(
        runtime_session,
        identity,
        [_host("10.0.0.9", "AA:00:00:00:00:01", "new")],
        at=T0 + timedelta(days=1),
    )

    headers = actor_headers(seeded_org.id, "admin")
    client.delete(f"/api/v1/scans/{newest}", headers=headers)

    runtime_session.expire_all()
    host = runtime_session.exec(select(HostRecord)).one()
    assert (host.ip, host.hostname, host.last_seen_at) == ("10.0.0.1", "old", T0)
    assert host.open_ports_count == 1
    assert host.highest_severity == "high"


@pytest.mark.parametrize("delete_newest", [True, False])
def test_scan_deletion_rebuilds_identity_and_seen_times(
    client: TestClient,
    runtime_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
    delete_newest: bool,
) -> None:
    mac = "AA:00:00:00:00:01"
    scans = [
        _ingest(runtime_session, identity, [_host("10.0.0.1", mac, "first")]),
        _ingest(
            runtime_session,
            identity,
            [_host("10.0.0.2", mac, "middle").model_copy(update={"vendor": "unknown"})],
            at=T0 + timedelta(days=1),
        ),
        _ingest(
            runtime_session,
            identity,
            [_host("10.0.0.3", mac, "last")],
            at=T0 + timedelta(days=2),
        ),
    ]
    for scan_id, name in ((scans[0], "old OS"), (scans[2], "new OS")):
        scan_host = runtime_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).one()
        scan_host.operating_system_json = {"name": name}
        runtime_session.add(scan_host)
    runtime_session.commit()
    host_id = _host_id(runtime_session, seeded_org.id, "10.0.0.3")

    response = client.delete(
        f"/api/v1/scans/{scans[-1] if delete_newest else scans[0]}",
        headers=actor_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 204
    runtime_session.expire_all()
    host = runtime_session.get(HostRecord, host_id)
    assert host is not None
    assert host.identity_key == f"mac:{mac}"
    assert host.mac == mac
    assert host.first_seen_at == T0 + timedelta(days=0 if delete_newest else 1)
    assert host.last_seen_at == T0 + timedelta(days=1 if delete_newest else 2)
    assert host.ip == ("10.0.0.2" if delete_newest else "10.0.0.3")
    assert host.hostname == ("middle" if delete_newest else "last")
    assert host.vendor == "vendor"
    assert host.operating_system_json == {
        "name": "old OS" if delete_newest else "new OS"
    }
    assert host.open_ports_count == 1
    assert host.highest_severity == "high"


def test_deleting_machine_keeps_scans_but_drops_its_rows(
    client: TestClient,
    runtime_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    headers = actor_headers(seeded_org.id, "admin")
    target = _host("10.0.0.1", "AA:00:00:00:00:01", "target")
    other = _host("10.0.0.2", "AA:00:00:00:00:02", "other")
    scans = [
        _ingest(runtime_session, identity, [target, other]),
        _ingest(runtime_session, identity, [target, other], at=T0 + timedelta(hours=1)),
    ]
    host_id = _host_id(runtime_session, seeded_org.id, "10.0.0.1")

    response = client.delete(f"/api/v1/hosts/{host_id}", headers=headers)

    assert response.status_code == 204
    for scan_id in scans:
        detail = client.get(f"/api/v1/scans/{scan_id}", headers=headers).json()
        assert [row["ip"] for row in detail["hosts"]] == ["10.0.0.2"]
    runtime_session.expire_all()
    assert runtime_session.exec(
        select(FindingRecord).where(FindingRecord.ip == "10.0.0.1")
    ).all() == []
    assert client.get(f"/api/v1/hosts/{host_id}", headers=headers).status_code == 404
    [entry] = _activity(runtime_session, seeded_org.id, "machines_deleted")
    assert entry.payload["machine"] == "target"

    _ingest(runtime_session, identity, [target], at=T0 + timedelta(hours=2))

    assert _host_id(runtime_session, seeded_org.id, "10.0.0.1") != host_id


def test_delete_all_machines_keeps_scans(
    client: TestClient,
    runtime_session: Session,
    identity: AgentIdentity,
    seeded_org: Org,
    actor_headers: Headers,
) -> None:
    scan_id = _ingest(
        runtime_session,
        identity,
        [HOST_A, _host("10.0.0.2", "AA:00:00:00:00:02", "b")],
    )

    headers = actor_headers(seeded_org.id, "admin")
    response = client.delete("/api/v1/hosts", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    runtime_session.expire_all()
    assert runtime_session.get(ScanRecord, scan_id) is not None
    assert runtime_session.exec(select(ScanHostRecord)).all() == []
    assert len(_activity(runtime_session, seeded_org.id, "machines_deleted")) == 1


@pytest.mark.parametrize(
    "path",
    ["/api/v1/scans", "/api/v1/scans/{id}", "/api/v1/hosts", "/api/v1/hosts/{id}"],
)
def test_viewer_cannot_delete(
    client: TestClient, seeded_org: Org, actor_headers: Headers, path: str
) -> None:
    response = client.delete(
        path.format(id=uuid4()), headers=actor_headers(seeded_org.id, "viewer")
    )

    assert response.status_code == 403


def test_other_org_scan_and_machine_are_not_found(
    client: TestClient,
    runtime_session: Session,
    administrative_session: Session,
    identity: AgentIdentity,
    actor_headers: Headers,
    seeded_org: Org,
) -> None:
    scan_id = _ingest(runtime_session, identity, [HOST_A])
    host_id = _host_id(runtime_session, seeded_org.id, "10.0.0.1")
    other_org = Org(name="Other Org")
    administrative_session.add(other_org)
    administrative_session.commit()
    headers = actor_headers(other_org.id, "admin")

    assert client.delete(f"/api/v1/scans/{scan_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/hosts/{host_id}", headers=headers).status_code == 404
    runtime_session.expire_all()
    assert runtime_session.get(ScanRecord, scan_id) is not None
    assert runtime_session.get(HostRecord, host_id) is not None
