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
