import pytest
from api.models.persistence import EpssRecord, KevRecord, RiskSnapshotRecord
from api.services.ai.context import ScanAINotReadyError, build_scan_ai_context
from read_factories import seed_read_graph


def test_context_uses_ranked_bounded_enriched_findings(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    other_finding = seeded["other_finding"]
    finding.cve_id = "CVE-2024-10001"
    finding.cvss_score = 9.8
    finding.confidence = "confirmed"
    other_finding.cve_id = "CVE-2024-10002"
    administrative_session.add(finding)
    administrative_session.add(other_finding)
    administrative_session.add(
        EpssRecord(
            cve_id=finding.cve_id,
            epss_score=0.91,
            percentile=0.99,
        )
    )
    administrative_session.add(
        KevRecord(
            cve_id=finding.cve_id,
            known_ransomware=True,
        )
    )
    administrative_session.add(
        RiskSnapshotRecord(
            finding_id=finding.id,
            confidence="confirmed",
            exploitability=0.95,
            risk_score=96,
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

    context = build_scan_ai_context(
        administrative_session,
        seeded["scan"],
        max_findings=1,
    )

    assert context is not None
    assert context.context_version == "1"
    assert context.scan_id == seeded["scan"].scan_id
    assert context.host_count == 2
    assert context.total_findings == 2
    assert context.scored_findings == 2
    assert context.confirmed_findings == 1
    assert context.kev_findings == 1
    assert context.average_risk_score == 58
    assert context.max_risk_score == 96
    assert len(context.top_findings) == 1

    top = context.top_findings[0]
    assert top.finding_id == finding.finding_id
    assert top.host_id == seeded["host"].id
    assert top.risk_score == 96
    assert top.cvss_score == 9.8
    assert top.epss_score == 0.91
    assert top.epss_percentile == 0.99
    assert top.is_kev is True
    assert top.known_ransomware is True


def test_context_requires_completed_scan(administrative_session):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].status = "processing"
    administrative_session.add(seeded["scan"])
    administrative_session.commit()

    with pytest.raises(ScanAINotReadyError):
        build_scan_ai_context(administrative_session, seeded["scan"])


@pytest.mark.parametrize("max_findings", [0, 16])
def test_context_rejects_invalid_finding_limit(
    administrative_session,
    max_findings,
):
    seeded = seed_read_graph(administrative_session)

    with pytest.raises(ValueError, match="max_findings must be between 1 and 15"):
        build_scan_ai_context(
            administrative_session,
            seeded["scan"],
            max_findings=max_findings,
        )
