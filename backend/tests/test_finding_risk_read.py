from api.models.persistence import RiskSnapshotRecord


def test_risk_is_returned_by_scan_findings_and_home(
    client, administrative_session, bearer_headers,
):
    from read_factories import seed_read_graph

    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    finding.confidence = "probable"
    administrative_session.add(finding)
    administrative_session.add(RiskSnapshotRecord(
        finding_id=finding.id, risk_score=71.25, exploitability=0.5,
        confidence="probable", rationale="severity=high, confidence=probable",
    ))
    administrative_session.commit()
    headers = bearer_headers(seeded["org"].id, "viewer")
    for path, key in (
        ("/api/v1/findings", "data"),
        (f"/api/v1/scans/{seeded['scan'].scan_id}", "findings"),
        ("/api/v1/home", "attention"),
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        rows = response.json()[key]
        if key == "attention":
            rows = rows["data"]
        item = next(
            row for row in rows if row["finding_id"] == str(finding.finding_id)
        )
        assert item["risk_score"] == 71.25
        assert item["confidence"] == "probable"
        assert item["exploitability"] == 0.5


def test_persisted_confidence_is_returned_without_a_risk_snapshot(
    client, administrative_session, bearer_headers,
):
    from read_factories import seed_read_graph

    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    finding.confidence = "probable"
    administrative_session.add(finding)
    administrative_session.commit()
    headers = bearer_headers(seeded["org"].id, "viewer")
    paths = (
        ("/api/v1/findings", "data"),
        (f"/api/v1/findings/{finding.finding_id}", None),
        (f"/api/v1/scans/{seeded['scan'].scan_id}", "findings"),
        (f"/api/v1/scans/{seeded['scan'].scan_id}/risk-summary", "top_findings"),
        ("/api/v1/home", "attention"),
    )

    for path, key in paths:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
        body = response.json()
        if key == "attention":
            rows = body[key]["data"]
        elif key is None:
            rows = [body]
        else:
            rows = body[key]
        item = next(row for row in rows if row["finding_id"] == str(finding.finding_id))
        assert item["confidence"] == "probable", path
        assert item["risk_score"] is None, path
        assert item["detection_method"] == "unknown", path
        assert item["evidence_status"] == "unknown", path


def test_findings_carry_risk_parts_feeds_and_the_cpe_product(
    client, administrative_session, bearer_headers,
):
    from api.models.persistence import (
        CPERecord,
        EpssRecord,
        KevRecord,
        PortRecord,
    )
    from api.services.risk import refresh_risk_snapshot
    from read_factories import seed_read_graph
    from sqlmodel import select

    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    port = administrative_session.exec(
        select(PortRecord).where(PortRecord.port == 80)
    ).first()
    finding.cve_id = "CVE-2026-0001"
    finding.confidence = "confirmed"
    finding.port_id = port.id
    administrative_session.add_all(
        [
            finding,
            EpssRecord(cve_id="CVE-2026-0001", epss_score=0.42),
            KevRecord(cve_id="CVE-2026-0001", known_ransomware=True),
            CPERecord(port_id=port.id, cpe="cpe:/a:hikvision:ds-2cd2:5.4.0"),
            CPERecord(port_id=port.id, cpe="cpe:/o:linux:linux_kernel"),
        ]
    )
    administrative_session.flush()
    snapshot = refresh_risk_snapshot(administrative_session, finding)
    administrative_session.commit()

    response = client.get(
        f"/api/v1/findings/{finding.finding_id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    body = response.json()
    assert body["epss_score"] == 0.42
    assert body["kev_listed"] is True
    assert body["known_ransomware"] is True
    assert body["product"] == "hikvision ds-2cd2"
    assert body["version"] == "5.4.0"
    breakdown = body["risk_breakdown"]
    assert breakdown == {
        "severity": 33.8,
        "likelihood": 24.3,
        "confidence": 15.0,
        "reachable": 5.0,
    }
    assert snapshot.risk_score == round(
        0.75 * 45 + snapshot.exploitability * 35 + 15 + 5, 2
    )
