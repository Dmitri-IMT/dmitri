from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pydantic
import pytest
from api.models.command import Agent, Command
from api.models.persistence import KevRecord, RiskSnapshotRecord, ScanRecord
from api.services.read import get_scan_detail
from read_factories import seed_read_graph
from sqlmodel import Session
from starlette.testclient import TestClient


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


def test_get_scan_by_id_happy_path(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
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


def test_get_scan_by_id_returns_scan_host_operating_system_snapshot(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    snapshot = {
        "name": "Linux 5",
        "accuracy": 91,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "5.X",
        "device_type": "general purpose",
        "cpes": ["cpe:/o:linux:linux_kernel:5"],
    }
    seeded["scan_host"].operating_system_json = snapshot
    seeded["host"].operating_system_json = {
        "name": "Linux 6",
        "accuracy": 98,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "6.X",
        "device_type": "general purpose",
        "cpes": ["cpe:/o:linux:linux_kernel:6"],
    }
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    row = next(
        host
        for host in response.json()["hosts"]
        if host["host_id"] == str(seeded["host"].id)
    )
    assert row["operating_system"] == snapshot


def test_scan_read_rejects_malformed_persisted_operating_system_snapshot(
    administrative_session: Session,
) -> None:
    seeded = seed_read_graph(administrative_session)
    seeded["scan_host"].operating_system_json = {
        "name": "Linux",
        "accuracy": 101,
        "cpes": [],
    }
    administrative_session.commit()

    with pytest.raises(pydantic.ValidationError):
        get_scan_detail(
            administrative_session,
            seeded["scan"].scan_id,
            org_id=seeded["org"].id,
        )


def test_get_scan_by_id_returns_industrial_service_snapshot(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    snapshot = [
        {
            "protocol": "modbus_tcp",
            "port": 502,
            "confidence": "confirmed",
            "evidence_sources": ["modbus-discover", "pymodbus"],
            "mapping_source": "generic_baseline",
            "units": [
                {
                    "unit_id": 1,
                    "status": "responding",
                    "device_identification": {
                        "vendor_name": "Schneider Electric",
                        "product_code": "TM221CE16T",
                    },
                }
            ],
        }
    ]
    seeded["scan_host"].industrial_services_json = snapshot
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    row = next(
        host
        for host in response.json()["hosts"]
        if host["host_id"] == str(seeded["host"].id)
    )
    assert row["industrial_services"][0]["port"] == 502
    assert row["industrial_services"][0]["units"][0]["device_identification"] == {
        "vendor_name": "Schneider Electric",
        "product_code": "TM221CE16T",
        "major_minor_revision": None,
        "vendor_url": None,
        "product_name": None,
        "model_name": None,
        "user_application_name": None,
        "objects": {},
    }


def test_get_scan_by_id_failed_body_has_error_code_and_command_id(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded["org"].id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.4.0/24",
        scan_mode="quick",
        status="failed",
        metadata_json={},
    )
    administrative_session.add(scan)
    administrative_session.flush()
    command = _seed_command(
        administrative_session,
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
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/scans/{uuid4()}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404


def test_get_scan_by_id_cross_org_returns_404_not_403(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/scans/{seeded['foreign_scan'].scan_id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404
    assert response.status_code != 403


def test_get_scan_risk_summary_is_bounded_and_evidence_bearing(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    other_finding = seeded["other_finding"]
    finding.cve_id = "CVE-2024-10001"
    finding.confidence = "confirmed"
    other_finding.cve_id = "CVE-2024-10002"
    administrative_session.add(finding)
    administrative_session.add(other_finding)
    administrative_session.add(
        KevRecord(cve_id=finding.cve_id, known_ransomware=False)
    )
    administrative_session.add(
        RiskSnapshotRecord(
            finding_id=finding.id,
            confidence="confirmed",
            exploitability=0.7,
            risk_score=80,
            rationale="severity=high, confidence=confirmed, kev=yes",
        )
    )
    administrative_session.add(
        RiskSnapshotRecord(
            finding_id=other_finding.id,
            confidence="tentative",
            exploitability=0.1,
            risk_score=20,
            rationale="severity=low, confidence=tentative, kev=no",
        )
    )
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/risk-summary",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "scan_id": str(seeded["scan"].scan_id),
        "total_findings": 2,
        "scored_findings": 2,
        "confirmed_findings": 1,
        "kev_findings": 1,
        "average_risk_score": 50.0,
        "max_risk_score": 80.0,
        "severity": {"critical": 0, "high": 1, "medium": 0, "low": 1},
        "top_findings": body["top_findings"],
    }
    assert [item["finding_id"] for item in body["top_findings"]] == [
        str(finding.finding_id),
        str(other_finding.finding_id),
    ]
    assert body["top_findings"][0]["evidence"] == finding.evidence
    assert body["top_findings"][0]["risk_rationale"].endswith("kev=yes")


def test_get_scan_risk_summary_hides_foreign_and_unknown_scans(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    headers = bearer_headers(seeded["org"].id, "admin")

    for scan_id in (seeded["foreign_scan"].scan_id, uuid4()):
        response = client.get(
            f"/api/v1/scans/{scan_id}/risk-summary", headers=headers
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_list_scans_empty_org_returns_200_not_404(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seed_read_graph(administrative_session)
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
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    now = datetime.now(timezone.utc)
    for offset in (1, 2):
        administrative_session.add(
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
    administrative_session.commit()

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
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
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
    administrative_session.add(empty_scan)
    administrative_session.commit()

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
    assert "agent_id" in row
    assert "box_name" in row
    assert "duration" in row


def test_list_scans_filters_by_agent_id(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    agent = Agent(
        org_id=seeded["org"].id,
        display_name="HQ",
        public_key=b"\x01" * 32,
    )
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)
    now = datetime.now(timezone.utc)
    owned = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded["org"].id,
        agent_id=agent.id,
        timestamp=now,
        subnet="10.9.0.0/24",
        scan_mode="quick",
        status="pending",
    )
    administrative_session.add(owned)
    administrative_session.commit()
    headers = bearer_headers(seeded["org"].id, "admin")
    response = client.get(
        f"/api/v1/scans?agent_id={agent.id}",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["data"][0]["scan_id"] == str(owned.scan_id)
    assert body["data"][0]["agent_id"] == str(agent.id)
    assert body["data"][0]["box_name"] == "HQ"


def test_get_scan_by_id_includes_box_and_duration_fields(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    headers = bearer_headers(seeded["org"].id, "viewer")
    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert "agent_id" in body
    assert "box_name" in body
    assert "duration" in body


@pytest.mark.parametrize(
    ("query",),
    (
        ("sort_by=nope",),
        ("sort_order=sideways",),
        ("status=bogus",),
    ),
)
def test_list_scans_invalid_query_returns_validation_error(
    client: TestClient, administrative_session: Session, bearer_headers, query: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/scans?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
