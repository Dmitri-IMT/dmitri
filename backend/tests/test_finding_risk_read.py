from uuid import uuid4

from api.models.persistence import FindingRecord, RiskSnapshotRecord
from api.services.read import findings_with_risk


def test_risk_snapshots_are_loaded_once_and_matched_by_finding_id():
    findings = [
        FindingRecord(
            id=index, scan_id=uuid4(), severity="medium", title="Finding",
            description="Description", recommendation="Recommendation",
            evidence="Evidence", dedupe_key=str(index),
        )
        for index in (1, 2, 3)
    ]
    snapshots = [
        RiskSnapshotRecord(
            finding_id=index, risk_score=score, exploitability=0,
            confidence="tentative", rationale="Evidence-based calculation",
        )
        for index, score in ((3, 80), (1, 0))
    ]

    class Session:
        calls = 0

        def exec(self, query):
            self.calls += 1
            assert query.compile().params["finding_id_1"] == [1, 2, 3]
            return self

        def all(self):
            return snapshots

    session = Session()
    result = findings_with_risk(session, [(finding, None) for finding in findings])
    assert session.calls == 1
    assert [item.risk_score for item in result] == [0, None, 80]
    assert result[0].exploitability == 0
    assert result[0].confidence == "tentative"
    assert result[1].risk_rationale is None
    assert result[2].risk_rationale == "Evidence-based calculation"
    assert findings_with_risk(session, []) == []
    assert session.calls == 1


def test_risk_is_returned_by_scan_findings_and_home(
    client, administrative_session, bearer_headers,
):
    from read_factories import seed_read_graph

    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
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
        item = next(row for row in rows if row["finding_id"] == str(finding.finding_id))
        assert item["risk_score"] == 71.25
        assert item["confidence"] == "probable"
        assert item["exploitability"] == 0.5
