import pytest
from api.models.persistence import EpssRecord, KevRecord, RiskSnapshotRecord
from api.schemas.ai import (
    AIProviderFindingExplanation,
    AIProviderRecommendedAction,
    ProviderScanAIAnalysis,
)
from api.services.ai.context import (
    ScanAINotReadyError,
    build_scan_ai_context,
    materialize_scan_ai_analysis,
)
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
    assert context.context_version == "3"
    assert context.host_count == 2
    assert context.total_findings == 2
    assert context.scored_findings == 2
    assert context.confirmed_findings == 1
    assert context.kev_findings == 1
    assert context.average_risk_score == 58
    assert context.max_risk_score == 96
    assert len(context.top_findings) == 1

    top = context.top_findings[0]
    assert top.finding_ref == "finding_1"
    assert top.machine_ref == "machine_1"
    assert top.risk_score == 96
    assert top.cvss_score == 9.8
    assert top.epss_score == 0.91
    assert top.epss_percentile == 0.99
    assert top.is_kev is True
    assert top.known_ransomware is True


@pytest.mark.parametrize(
    ("terminated_by", "stopped_by"),
    [
        ("user_cancel", "operator"),
        ("timeout", "timeout"),
        ("error", "error"),
        (None, None),
    ],
)
def test_context_maps_partial_scan_termination(
    administrative_session,
    terminated_by,
    stopped_by,
):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].metadata_json = {
        "partial_result": True,
        "terminated_by": terminated_by,
    }

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    assert context.context_version == "3"
    assert context.partial_result is True
    assert context.stopped_by == stopped_by


def test_context_marks_complete_scan_as_not_partial(administrative_session):
    seeded = seed_read_graph(administrative_session)

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    assert context.partial_result is False
    assert context.stopped_by is None


def test_context_sends_only_public_facts_and_placeholders(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    finding.cve_id = "CVE-2024-10001"
    administrative_session.add(finding)
    administrative_session.commit()

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    payload = context.model_dump_json()
    for value in (
        str(seeded["scan"].scan_id),
        seeded["scan"].subnet,
        str(seeded["host"].id),
        str(finding.finding_id),
        str(finding.ip),
        finding.title,
        finding.description,
        finding.recommendation,
        finding.evidence,
    ):
        assert value not in payload
    assert '"finding_ref":"finding_1"' in payload
    assert '"machine_ref":"machine_1"' in payload


def test_materialize_analysis_replaces_local_references(administrative_session):
    seeded = seed_read_graph(administrative_session)
    context = build_scan_ai_context(administrative_session, seeded["scan"])
    assert context is not None

    analysis = materialize_scan_ai_analysis(
        context,
        ProviderScanAIAnalysis(
            executive_summary="finding_1 needs attention.",
            overall_assessment="machine_1 has one recorded vulnerability.",
            plain_language_summary="Review finding_1 with the machine owner.",
            priority_actions=[
                AIProviderRecommendedAction(
                    priority="high",
                    title="Review finding_1",
                    description="Ask the owner of machine_1 to review it.",
                    related_finding_refs=["finding_1"],
                )
            ],
            important_findings=[
                AIProviderFindingExplanation(
                    finding_ref="finding_1",
                    why_it_matters="finding_1 is exposed.",
                    plain_language_explanation="machine_1 needs a review.",
                    recommendation="Review finding_1.",
                    evidence_used=["The scan recorded finding_1."],
                    uncertainty=None,
                )
            ],
            uncertainties=[],
        ),
    )

    assert analysis.important_findings[0].finding_id == seeded["finding"].finding_id
    assert analysis.priority_actions[0].related_finding_ids == [
        seeded["finding"].finding_id
    ]
    assert "finding_1" not in analysis.model_dump_json()
    assert "machine_1" not in analysis.model_dump_json()


def test_materialize_analysis_rejects_unknown_reference(administrative_session):
    seeded = seed_read_graph(administrative_session)
    context = build_scan_ai_context(administrative_session, seeded["scan"])
    assert context is not None

    analysis = ProviderScanAIAnalysis(
        executive_summary="finding_99 needs attention.",
        overall_assessment="The scan recorded a vulnerability.",
        plain_language_summary="Review the recorded vulnerability.",
        priority_actions=[],
        important_findings=[],
        uncertainties=[],
    )

    with pytest.raises(ValueError, match="unknown reference"):
        materialize_scan_ai_analysis(context, analysis)


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
