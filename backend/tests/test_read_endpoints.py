from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel
from starlette.testclient import TestClient


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(session: Session) -> TestClient:
    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed(session: Session) -> dict:
    now = datetime.now(timezone.utc)
    scan = ScanRecord(
        scan_id=uuid4(),
        timestamp=now,
        subnet="192.168.1.0/24",
        scan_mode="quick",
        status="completed",
        metadata_json={},
    )
    session.add(scan)
    session.flush()

    host = HostRecord(
        identity_key="aa:bb:cc:dd:ee:ff",
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        hostname="host-a",
        vendor="Acme",
        open_ports_count=1,
        highest_severity="high",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(host)
    session.flush()

    scan_host = ScanHostRecord(
        scan_id=scan.scan_id,
        host_id=host.id,
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        hostname="host-a",
        vendor="Acme",
    )
    session.add(scan_host)
    session.flush()

    port = PortRecord(
        scan_host_id=scan_host.id,
        port=80,
        protocol="tcp",
        state="open",
    )
    session.add(port)
    session.flush()

    service = ServiceRecord(port_id=port.id, name="http", version="1.0")
    session.add(service)

    finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan.scan_id,
        scan_host_id=scan_host.id,
        ip="192.168.1.10",
        port=80,
        protocol="tcp",
        service="http",
        severity="high",
        title="Vulnerable service",
        description="A vulnerable service was found.",
        recommendation="Patch it.",
        evidence="Some evidence.",
        dedupe_key="dedupe-1",
    )
    session.add(finding)
    session.flush()

    other_host = HostRecord(
        identity_key="11:22:33:44:55:66",
        ip="192.168.1.20",
        mac="11:22:33:44:55:66",
        hostname="host-b",
        vendor="Acme",
        open_ports_count=1,
        highest_severity="low",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(other_host)
    session.flush()

    other_scan_host = ScanHostRecord(
        scan_id=scan.scan_id,
        host_id=other_host.id,
        ip="192.168.1.20",
        mac="11:22:33:44:55:66",
        hostname="host-b",
        vendor="Acme",
    )
    session.add(other_scan_host)
    session.flush()

    other_finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan.scan_id,
        scan_host_id=other_scan_host.id,
        ip="192.168.1.20",
        port=22,
        protocol="tcp",
        service="ssh",
        severity="low",
        title="Weak cipher",
        description="A weak cipher was found.",
        recommendation="Reconfigure it.",
        evidence="Some evidence.",
        dedupe_key="dedupe-2",
    )
    session.add(other_finding)
    session.commit()

    return {
        "scan": scan,
        "host": host,
        "finding": finding,
        "other_host": other_host,
        "other_finding": other_finding,
    }


def test_list_hosts_happy_path(client: TestClient, session: Session) -> None:
    seeded = _seed(session)
    response = client.get("/api/v1/hosts")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    host_ids = {row["host_id"] for row in body["data"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}
    seeded_row = next(
        row for row in body["data"] if row["host_id"] == str(seeded["host"].id)
    )
    assert seeded_row["first_seen_at"] == seeded["host"].first_seen_at.isoformat()


def test_get_host_by_id_happy_path(client: TestClient, session: Session) -> None:
    seeded = _seed(session)
    response = client.get(f"/api/v1/hosts/{seeded['host'].id}")
    assert response.status_code == 200
    body = response.json()
    assert body["host_id"] == str(seeded["host"].id)
    assert body["first_seen_at"] == seeded["host"].first_seen_at.isoformat()
    assert body["last_seen_at"] == seeded["host"].last_seen_at.isoformat()
    assert body["hostname"] == "host-a"
    assert len(body["scan_history"]) == 1
    assert body["scan_history"][0]["scan_id"] == str(seeded["scan"].scan_id)


def test_get_host_by_id_unknown_returns_404(
    client: TestClient, session: Session
) -> None:
    _seed(session)
    response = client.get(f"/api/v1/hosts/{uuid4()}")
    assert response.status_code == 404


def test_get_scan_by_id_happy_path(client: TestClient, session: Session) -> None:
    seeded = _seed(session)
    response = client.get(f"/api/v1/scans/{seeded['scan'].scan_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == str(seeded["scan"].scan_id)
    assert len(body["hosts"]) == 2
    host_ids = {row["host_id"] for row in body["hosts"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}
    for row in body["hosts"]:
        assert row["host_id"] is not None
    finding_host_ids = {f["host_id"] for f in body["findings"]}
    assert finding_host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}


def test_get_scan_by_id_unknown_returns_404(
    client: TestClient, session: Session
) -> None:
    _seed(session)
    response = client.get(f"/api/v1/scans/{uuid4()}")
    assert response.status_code == 404


def test_list_findings_filtered_by_host_id(
    client: TestClient, session: Session
) -> None:
    seeded = _seed(session)
    response = client.get(f"/api/v1/findings?host_id={seeded['host'].id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    finding = body["data"][0]
    assert finding["finding_id"] == str(seeded["finding"].finding_id)
    assert finding["host_id"] == str(seeded["host"].id)
    assert seeded["host"].highest_severity in {f["severity"] for f in body["data"]}
    assert str(seeded["other_host"].id) not in {f["host_id"] for f in body["data"]}
    assert seeded["other_finding"].finding_id not in {
        UUID(f["finding_id"]) for f in body["data"]
    }


def test_list_findings_unfiltered_returns_all_hosts(
    client: TestClient, session: Session
) -> None:
    seeded = _seed(session)
    response = client.get("/api/v1/findings")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    host_ids = {f["host_id"] for f in body["data"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}
