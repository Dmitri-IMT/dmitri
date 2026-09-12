from __future__ import annotations

from api.models.identity import Org
from api.models.persistence import HostRecord
from api.schemas.read import IndustrialServiceView, ModbusUnitView
from sqlmodel import Session, select
from starlette.testclient import TestClient
from test_industrial_persistence import SAMPLE_DIGEST, _host, _persist, _scan


def test_host_and_scan_read_match_ingested_industrial_observation(
    client: TestClient,
    administrative_session: Session,
    bearer_headers,
    seeded_org: Org,
    provisioned_agent,
) -> None:
    scan = _scan([_host()])
    _persist(administrative_session, scan, seeded_org, provisioned_agent)
    headers = bearer_headers(seeded_org.id, "viewer")

    host = administrative_session.exec(select(HostRecord)).one()
    host_body = client.get(f"/api/v1/hosts/{host.id}", headers=headers).json()
    scan_body = client.get(f"/api/v1/scans/{scan.scan_id}", headers=headers).json()

    ingested = scan.hosts[0].industrial_services[0]
    for services in (
        host_body["industrial_services"],
        scan_body["hosts"][0]["industrial_services"],
    ):
        assert len(services) == 1
        service = services[0]
        assert service["protocol"] == ingested.protocol
        assert service["port"] == ingested.port
        assert service["confidence"] == ingested.confidence
        assert service["mapping_source"] == ingested.mapping_source
        assert service["evidence_sources"] == ingested.evidence_sources
        assert "write_requests_sent" not in service
        assert "values" not in service
        units = service["units"]
        assert [unit["unit_id"] for unit in units] == [1, 2]
        assert units[0]["identification"]["product_name"] == "Modicon M580"
        assert units[0]["address_ranges"][0]["status"] == "readable"
        assert units[0]["address_ranges"][0]["value_digest"] == SAMPLE_DIGEST
        assert "values" not in units[0]["address_ranges"][0]
        assert units[1]["identification"]["product_name"] == "S7-1200"

    assert host_body["unreadable_fields"] == []
    assert scan_body["hosts"][0]["unreadable_fields"] == []


def test_industrial_read_is_isolated_by_org(
    client: TestClient,
    administrative_session: Session,
    bearer_headers,
    seeded_org: Org,
    provisioned_agent,
) -> None:
    scan = _scan([_host()])
    _persist(administrative_session, scan, seeded_org, provisioned_agent)
    host = administrative_session.exec(select(HostRecord)).one()

    other = Org(name="Other Org")
    administrative_session.add(other)
    administrative_session.commit()
    administrative_session.refresh(other)
    other_headers = bearer_headers(other.id, "admin")

    assert (
        client.get(f"/api/v1/hosts/{host.id}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/scans/{scan.scan_id}", headers=other_headers).status_code
        == 404
    )
    listed = client.get("/api/v1/hosts", headers=other_headers).json()
    assert listed["total"] == 0
    listed_scans = client.get("/api/v1/scans", headers=other_headers).json()
    assert listed_scans["total"] == 0


def test_industrial_service_view_has_no_process_or_validation_fields() -> None:
    dumped = IndustrialServiceView.model_json_schema()
    assert "values" not in dumped["properties"]
    assert "validations" not in dumped["properties"]
    assert "write_requests_sent" not in dumped["properties"]
    unit_schema = ModbusUnitView.model_json_schema()
    assert "validations" not in unit_schema["properties"]
    assert "ot_digest_key" not in dumped["properties"]
