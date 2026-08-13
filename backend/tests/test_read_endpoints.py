from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from api.core.config import get_settings
from api.db.session import get_session
from api.main import app
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
    utc_now,
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

    org = Org(name="Org A")
    session.add(org)
    session.flush()

    other_org = Org(name="Org B")
    session.add(other_org)
    session.flush()

    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org.id,
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
        org_id=org.id,
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
        org_id=org.id,
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
    session.flush()

    foreign_scan = ScanRecord(
        scan_id=uuid4(),
        org_id=other_org.id,
        timestamp=now,
        subnet="10.0.0.0/24",
        scan_mode="quick",
        status="completed",
        metadata_json={},
    )
    session.add(foreign_scan)
    session.flush()

    foreign_host = HostRecord(
        identity_key="ff:ff:ff:ff:ff:ff",
        org_id=other_org.id,
        ip="10.0.0.10",
        mac="ff:ff:ff:ff:ff:ff",
        hostname="host-foreign",
        vendor="Acme",
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(foreign_host)
    session.flush()

    foreign_scan_host = ScanHostRecord(
        scan_id=foreign_scan.scan_id,
        host_id=foreign_host.id,
        ip="10.0.0.10",
        mac="ff:ff:ff:ff:ff:ff",
        hostname="host-foreign",
        vendor="Acme",
    )
    session.add(foreign_scan_host)
    session.flush()

    foreign_finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=foreign_scan.scan_id,
        scan_host_id=foreign_scan_host.id,
        ip="10.0.0.10",
        port=443,
        protocol="tcp",
        service="https",
        severity="low",
        title="Foreign finding",
        description="Belongs to another org.",
        recommendation="N/A",
        evidence="N/A",
        dedupe_key="dedupe-foreign",
    )
    session.add(foreign_finding)
    session.commit()

    return {
        "org": org,
        "other_org": other_org,
        "scan": scan,
        "host": host,
        "finding": finding,
        "other_host": other_host,
        "other_finding": other_finding,
        "foreign_scan": foreign_scan,
        "foreign_host": foreign_host,
        "foreign_finding": foreign_finding,
    }


def _seed_command(
    session: Session,
    org_id,
    scan: ScanRecord,
    *,
    status: str,
    error_code: str | None = None,
) -> Command:
    agent = Agent(
        org_id=org_id,
        display_name="scan-agent",
        public_key=b"\x01" * 32,
    )
    session.add(agent)
    session.flush()
    command = Command(
        org_id=org_id,
        agent_id=agent.id,
        scan_id=scan.scan_id,
        scan_mode=scan.scan_mode,
        subnet=scan.subnet,
        status=status,
        error_code=error_code,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


READ_PATHS = (
    "/api/v1/hosts",
    "/api/v1/hosts/{host_id}",
    "/api/v1/scans",
    "/api/v1/scans/{scan_id}",
    "/api/v1/findings",
)

LIST_ENDPOINTS = ("/api/v1/scans", "/api/v1/findings")


def _resolved_path(path: str, seeded: dict) -> str:
    return path.format(
        host_id=seeded["host"].id, scan_id=seeded["scan"].scan_id
    )


def _expired_bearer_headers(org_id: UUID, role: str) -> dict[str, str]:
    settings = get_settings()
    now = utc_now()
    claims = {
        "sub": str(uuid4()),
        "org_id": str(org_id),
        "role": role,
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=1),
    }
    token = jwt.encode(
        claims, settings.jwt_signing_secret.get_secret_value(), algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_without_bearer_returns_401(
    client: TestClient, session: Session, path: str
) -> None:
    seeded = _seed(session)
    response = client.get(_resolved_path(path, seeded))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_with_garbage_bearer_returns_401(
    client: TestClient, session: Session, path: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        _resolved_path(path, seeded),
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_list_hosts_happy_path(
    client: TestClient, session: Session, bearer_headers, role: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        "/api/v1/hosts", headers=bearer_headers(seeded["org"].id, role)
    )
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


def test_list_hosts_pages_beyond_the_first_twenty(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    now = datetime.now(timezone.utc)
    for index in range(23):
        session.add(
            HostRecord(
                identity_key=f"paging-{index}",
                org_id=seeded["org"].id,
                ip=f"192.168.9.{index + 1}",
                mac=f"aa:bb:cc:00:00:{index:02x}",
                hostname=f"paged-host-{index}",
                vendor="Acme",
                open_ports_count=0,
                highest_severity=None,
                first_seen_at=now,
                last_seen_at=now - timedelta(minutes=index + 1),
            )
        )
    session.commit()

    headers = bearer_headers(seeded["org"].id, "admin")
    first = client.get("/api/v1/hosts?page=1&per_page=20", headers=headers)
    second = client.get("/api/v1/hosts?page=2&per_page=20", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()

    assert first_body["total"] == 25
    assert second_body["total"] == 25
    assert len(first_body["data"]) == 20
    assert len(second_body["data"]) == 5
    assert second_body["page"] == 2

    first_ids = {row["host_id"] for row in first_body["data"]}
    second_ids = {row["host_id"] for row in second_body["data"]}
    assert first_ids.isdisjoint(second_ids)
    assert len(first_ids | second_ids) == 25


def test_get_host_by_id_happy_path(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["host_id"] == str(seeded["host"].id)
    assert body["first_seen_at"] == seeded["host"].first_seen_at.isoformat()
    assert body["last_seen_at"] == seeded["host"].last_seen_at.isoformat()
    assert body["hostname"] == "host-a"
    assert len(body["scan_history"]) == 1
    assert body["scan_history"][0]["scan_id"] == str(seeded["scan"].scan_id)


def test_mac_less_host_is_listed_and_readable(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    now = datetime.now(timezone.utc)
    mac_less = HostRecord(
        identity_key="ip:192.168.1.30",
        org_id=seeded["org"].id,
        ip="192.168.1.30",
        mac=None,
        hostname="host-routed",
        vendor="Unknown",
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(mac_less)
    session.commit()

    headers = bearer_headers(seeded["org"].id, "admin")
    listed = client.get("/api/v1/hosts", headers=headers)
    assert listed.status_code == 200
    row = next(
        item for item in listed.json()["data"] if item["host_id"] == str(mac_less.id)
    )
    assert row["mac"] is None

    detail = client.get(f"/api/v1/hosts/{mac_less.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["mac"] is None


def test_get_host_by_id_unknown_returns_404(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/hosts/{uuid4()}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404


def test_get_host_by_id_cross_org_returns_404_not_403(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/hosts/{seeded['foreign_host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404
    assert response.status_code != 403


def test_get_scan_by_id_happy_path(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    headers = bearer_headers(seeded["org"].id, "viewer")
    response = client.get(f"/api/v1/scans/{seeded['scan'].scan_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == str(seeded["scan"].scan_id)
    assert len(body["hosts"]) == 2
    host_ids = {row["host_id"] for row in body["hosts"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}
    for row in body["hosts"]:
        assert row["host_id"] is not None
        resolved = client.get(f"/api/v1/hosts/{row['host_id']}", headers=headers)
        assert resolved.status_code == 200
        assert resolved.json()["host_id"] == row["host_id"]
        assert resolved.json()["ip"] == row["ip"]

    expected_finding_host_ids = {
        str(seeded["finding"].finding_id): str(seeded["host"].id),
        str(seeded["other_finding"].finding_id): str(seeded["other_host"].id),
    }
    assert {f["finding_id"] for f in body["findings"]} == set(
        expected_finding_host_ids
    )
    for finding in body["findings"]:
        assert finding["host_id"] == expected_finding_host_ids[finding["finding_id"]]
    assert body["error_code"] is None


def test_get_scan_by_id_failed_body_has_error_code_and_command_id(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded["org"].id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.4.0/24",
        scan_mode="quick",
        status="failed",
        metadata_json={},
    )
    session.add(scan)
    session.flush()
    command = _seed_command(
        session,
        seeded["org"].id,
        scan,
        status="failed",
        error_code="scan_failed",
    )

    response = client.get(
        f"/api/v1/scans/{scan.scan_id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error_code"] == "scan_failed"
    assert body["command_id"] == str(command.id)


def test_get_scan_by_id_unknown_returns_404(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/scans/{uuid4()}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404


def test_get_scan_by_id_cross_org_returns_404_not_403(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/scans/{seeded['foreign_scan'].scan_id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404
    assert response.status_code != 403


def test_list_findings_filtered_by_host_id(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/findings?host_id={seeded['host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
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
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        "/api/v1/findings", headers=bearer_headers(seeded["org"].id, "viewer")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    host_ids = {f["host_id"] for f in body["data"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}


def test_list_findings_filtered_by_foreign_host_id_returns_empty(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/findings?host_id={seeded['foreign_host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_with_expired_bearer_returns_401(
    client: TestClient, session: Session, path: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        _resolved_path(path, seeded),
        headers=_expired_bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_with_viewer_token_never_returns_403(
    client: TestClient, session: Session, bearer_headers, path: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        _resolved_path(path, seeded), headers=bearer_headers(seeded["org"].id, "viewer")
    )
    assert response.status_code != 403
    assert response.status_code == 200


def test_nonexistent_org_token_list_hosts_returns_empty(
    client: TestClient, session: Session, bearer_headers
) -> None:
    _seed(session)
    response = client.get("/api/v1/hosts", headers=bearer_headers(uuid4(), "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_nonexistent_org_token_list_findings_returns_empty(
    client: TestClient, session: Session, bearer_headers
) -> None:
    _seed(session)
    response = client.get("/api/v1/findings", headers=bearer_headers(uuid4(), "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_nonexistent_org_token_get_host_returns_404(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}", headers=bearer_headers(uuid4(), "admin")
    )
    assert response.status_code == 404


def test_nonexistent_org_token_get_scan_returns_404(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}",
        headers=bearer_headers(uuid4(), "admin"),
    )
    assert response.status_code == 404


def test_list_scans_empty_org_returns_200_not_404(
    client: TestClient, session: Session, bearer_headers
) -> None:
    _seed(session)
    response = client.get(
        "/api/v1/scans", headers=bearer_headers(uuid4(), "admin")
    )
    assert response.status_code == 200
    assert response.status_code != 404
    assert response.status_code != 403
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_list_scans_page_past_end_returns_empty_200(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    now = datetime.now(timezone.utc)
    for offset in (1, 2):
        session.add(
            ScanRecord(
                scan_id=uuid4(),
                org_id=seeded["org"].id,
                timestamp=now - timedelta(hours=offset),
                subnet="192.168.2.0/24",
                scan_mode="quick",
                status="completed",
                metadata_json={},
            )
        )
    session.commit()

    response = client.get(
        "/api/v1/scans?page=5&per_page=20",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert response.status_code == 200
    assert response.status_code != 404
    assert response.status_code != 403
    body = response.json()
    assert body["data"] == []
    assert body["total"] == 3


def test_list_scans_zero_finding_scan_reports_null_highest_severity(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    now = datetime.now(timezone.utc)
    empty_scan = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded["org"].id,
        timestamp=now - timedelta(days=1),
        subnet="192.168.3.0/24",
        scan_mode="quick",
        status="completed",
        metadata_json={},
    )
    session.add(empty_scan)
    session.commit()

    response = client.get(
        "/api/v1/scans",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    body = response.json()
    row = next(
        item for item in body["data"] if item["scan_id"] == str(empty_scan.scan_id)
    )
    assert row["finding_count"] == 0
    assert row["highest_severity"] is None


def test_list_findings_critical_filter_empty_returns_200(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/findings?scan_id={seeded['scan'].scan_id}&severity=critical",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    assert response.status_code != 404
    assert response.status_code != 403
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_list_findings_filtered_by_foreign_scan_id_returns_empty(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/findings?scan_id={seeded['foreign_scan'].scan_id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    assert response.status_code != 404
    assert response.status_code != 403
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_list_findings_filtered_by_foreign_scan_and_host_returns_empty(
    client: TestClient, session: Session, bearer_headers
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/findings?scan_id={seeded['foreign_scan'].scan_id}"
        f"&host_id={seeded['foreign_host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    assert response.status_code != 404
    assert response.status_code != 403
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []
    assert seeded["foreign_finding"].finding_id not in {
        UUID(item["finding_id"]) for item in body["data"]
    }


@pytest.mark.parametrize("endpoint", LIST_ENDPOINTS)
@pytest.mark.parametrize(
    "query",
    ("per_page=101", "per_page=0", "page=0", "page=-1"),
)
def test_list_invalid_paging_returns_validation_error(
    client: TestClient,
    session: Session,
    bearer_headers,
    endpoint: str,
    query: str,
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"{endpoint}?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("endpoint", LIST_ENDPOINTS)
def test_list_per_page_at_max_succeeds(
    client: TestClient, session: Session, bearer_headers, endpoint: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"{endpoint}?per_page=100",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("query",),
    (
        ("sort_by=nope",),
        ("sort_order=sideways",),
        ("status=bogus",),
    ),
)
def test_list_scans_invalid_query_returns_validation_error(
    client: TestClient, session: Session, bearer_headers, query: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/scans?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    ("query",),
    (
        ("severity=urgent",),
        ("scan_id=not-a-uuid",),
    ),
)
def test_list_findings_invalid_query_returns_validation_error(
    client: TestClient, session: Session, bearer_headers, query: str
) -> None:
    seeded = _seed(session)
    response = client.get(
        f"/api/v1/findings?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
