from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from api.models.persistence import (
    HostFindingRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
)
from read_factories import make_finding, seed_read_graph
from sqlmodel import Session, select
from starlette.testclient import TestClient


def test_list_findings_filtered_by_host_id(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
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
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        "/api/v1/findings", headers=bearer_headers(seeded["org"].id, "viewer")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    host_ids = {f["host_id"] for f in body["data"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}


def test_list_findings_filtered_by_foreign_host_id_returns_empty(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/findings?host_id={seeded['foreign_host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_list_findings_critical_filter_empty_returns_200(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
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
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
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
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
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


@pytest.mark.parametrize(
    ("query",),
    (
        ("severity=urgent",),
        ("scan_id=not-a-uuid",),
    ),
)
def test_list_findings_invalid_query_returns_validation_error(
    client: TestClient, administrative_session: Session, bearer_headers, query: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/findings?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def _rename(session: Session, host, *, current: str, at_scan_time: str) -> None:
    host.hostname = current
    scan_host = session.exec(
        select(ScanHostRecord).where(ScanHostRecord.host_id == host.id)
    ).one()
    scan_host.hostname = at_scan_time
    session.add(host)
    session.add(scan_host)
    session.commit()


def test_finding_names_the_machines_current_name_after_a_rename(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    _rename(
        administrative_session,
        seeded["host"],
        current="renamed-machine",
        at_scan_time="name-at-scan-time",
    )

    headers = bearer_headers(seeded["org"].id, "admin")
    listed = client.get(
        f"/api/v1/findings?host_id={seeded['host'].id}", headers=headers
    )
    assert listed.status_code == 200
    assert [row["host_hostname"] for row in listed.json()["data"]] == [
        "renamed-machine"
    ]

    detail = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}", headers=headers
    )
    assert detail.status_code == 200
    row = next(
        item
        for item in detail.json()["findings"]
        if item["finding_id"] == str(seeded["finding"].finding_id)
    )
    assert row["host_hostname"] == "renamed-machine"


def test_finding_without_an_identifiable_machine_keeps_the_address(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    hostless = make_finding(
        administrative_session,
        seeded["scan"].scan_id,
        None,
        "dedupe-hostless",
        ip="192.168.1.99",
    )

    response = client.get(
        "/api/v1/findings", headers=bearer_headers(seeded["org"].id, "admin")
    )
    assert response.status_code == 200
    row = next(
        item
        for item in response.json()["data"]
        if item["finding_id"] == str(hostless.finding_id)
    )
    assert row["host_hostname"] is None
    assert row["host_id"] is None
    assert row["host_ip"] == "192.168.1.99"
    assert row["first_seen_at"] is None


def test_finding_first_seen_at_is_null_until_the_machine_has_a_problem_life(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    first_seen = datetime.now(timezone.utc) - timedelta(days=30)
    administrative_session.add(
        HostFindingRecord(
            host_id=seeded["host"].id,
            dedupe_key="dedupe-1",
            first_seen_at=first_seen,
            last_seen_at=datetime.now(timezone.utc),
            fixed_at=None,
        )
    )
    administrative_session.commit()

    response = client.get(
        "/api/v1/findings", headers=bearer_headers(seeded["org"].id, "admin")
    )
    assert response.status_code == 200
    rows = {item["finding_id"]: item for item in response.json()["data"]}
    lived = rows[str(seeded["finding"].finding_id)]
    unlived = rows[str(seeded["other_finding"].finding_id)]

    assert datetime.fromisoformat(lived["first_seen_at"]) == first_seen
    assert lived["fixed_at"] is None
    assert unlived["first_seen_at"] is None


def test_get_finding_by_id_returns_evidence_and_risk(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    administrative_session.add(
        RiskSnapshotRecord(
            finding_id=finding.id,
            confidence="confirmed",
            exploitability=0.62,
            risk_score=81.5,
            rationale="severity=high, confidence=confirmed, kev=yes",
        )
    )
    administrative_session.commit()

    response = client.get(
        f"/api/v1/findings/{finding.finding_id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["finding_id"] == str(finding.finding_id)
    assert body["host_id"] == str(seeded["host"].id)
    assert body["evidence"] == finding.evidence
    assert body["recommendation"] == finding.recommendation
    assert body["risk_score"] == 81.5
    assert body["exploitability"] == 0.62
    assert body["confidence"] == "confirmed"


def test_get_finding_by_id_hides_foreign_and_unknown_ids(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    headers = bearer_headers(seeded["org"].id, "admin")

    for finding_id in (seeded["foreign_finding"].finding_id, uuid4()):
        response = client.get(f"/api/v1/findings/{finding_id}", headers=headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
