from __future__ import annotations

from api.models.identity import Org
from api.models.persistence import (
    HostRecord,
    IndustrialServiceRecord,
    ModbusUnitRecord,
    ScanHostRecord,
)
from sqlmodel import Session, select
from starlette.testclient import TestClient
from test_industrial_persistence import _host, _persist, _scan


def test_junk_json_degrades_without_failing_the_list(
    client: TestClient,
    administrative_session: Session,
    bearer_headers,
    seeded_org: Org,
    provisioned_agent,
    monkeypatch,
) -> None:
    scan = _scan(
        [_host("192.168.1.50"), _host("192.168.1.51", mac="00:80:F4:11:22:44")]
    )
    _persist(administrative_session, scan, seeded_org, provisioned_agent)
    # Keep the fixture's hosts in the active group regardless of today's date.
    monkeypatch.setattr("api.services.read.utc_now", lambda: scan.timestamp)

    broken_host = administrative_session.exec(
        select(HostRecord).where(HostRecord.ip == "192.168.1.50")
    ).one()
    broken_host.operating_system_json = {"name": "not-an-os"}
    administrative_session.add(broken_host)
    scan_host = administrative_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.ip == "192.168.1.50")
    ).one()
    scan_host.operating_system_json = {"name": "not-an-os"}
    administrative_session.add(scan_host)

    unit = administrative_session.exec(
        select(ModbusUnitRecord)
        .join(IndustrialServiceRecord)
        .join(ScanHostRecord)
        .where(ScanHostRecord.ip == "192.168.1.50")
        .where(ModbusUnitRecord.unit_id == 1)
    ).one()
    unit.identification_json = {"unexpected": True}
    administrative_session.add(unit)
    administrative_session.commit()

    headers = bearer_headers(seeded_org.id, "viewer")
    listed = client.get("/api/v1/hosts", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    ips = {row["ip"] for row in body["data"]}
    assert ips == {"192.168.1.50", "192.168.1.51"}
    broken_row = next(row for row in body["data"] if row["ip"] == "192.168.1.50")
    healthy_row = next(row for row in body["data"] if row["ip"] == "192.168.1.51")
    assert broken_row["operating_system"] is None
    assert "operating_system" in broken_row["unreadable_fields"]
    assert healthy_row["unreadable_fields"] == []

    detail = client.get(f"/api/v1/hosts/{broken_host.id}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert "operating_system" in detail_body["unreadable_fields"]
    assert "identification" in detail_body["unreadable_fields"]
    unit_one = detail_body["industrial_services"][0]["units"][0]
    assert unit_one["identification"] is None

    scan_detail = client.get(f"/api/v1/scans/{scan.scan_id}", headers=headers)
    assert scan_detail.status_code == 200
    scan_host_view = next(
        row
        for row in scan_detail.json()["hosts"]
        if row["ip"] == "192.168.1.50"
    )
    assert scan_host_view["operating_system"] is None
    assert "operating_system" in scan_host_view["unreadable_fields"]
    assert "identification" in scan_host_view["unreadable_fields"]
