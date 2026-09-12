from datetime import datetime, timezone
from ipaddress import IPv4Address
from uuid import uuid4

import pytest
from api.schemas.read import SeverityBreakdown
from api.services.ai.analyzer import generate_scan_analysis
from api.services.ai.schemas import (
    AIFindingContext,
    AIFindingExplanation,
    AIRecommendedAction,
    ScanAIAnalysis,
    ScanAIContext,
)
from api.services.ai.validation import AIAnalysisValidationError
from pydantic import ValidationError


def _context() -> ScanAIContext:
    finding_id = uuid4()
    return ScanAIContext(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        duration_seconds=30,
        host_count=1,
        total_findings=1,
        scored_findings=1,
        confirmed_findings=1,
        kev_findings=0,
        average_risk_score=75,
        max_risk_score=75,
        severity=SeverityBreakdown(high=1),
        top_findings=[
            AIFindingContext(
                finding_id=finding_id,
                host_id=uuid4(),
                host_ip=IPv4Address("192.168.1.10"),
                port=443,
                protocol="tcp",
                service="https",
                cve_id="CVE-2024-10001",
                cvss_score=8.1,
                severity="high",
                confidence="confirmed",
                risk_score=75,
                exploitability=0.6,
                epss_score=0.5,
                epss_percentile=0.8,
                is_kev=False,
                known_ransomware=False,
                title="Vulnerable HTTPS service",
                description="A vulnerable HTTPS service was detected.",
                recommendation="Have a professional validate and update the service.",
                evidence="NVD validated the supplied CVE.",
                references=["https://example.test/CVE-2024-10001"],
            )
        ],
    )


def _analysis(finding_id) -> ScanAIAnalysis:
    return ScanAIAnalysis(
        executive_summary="One important issue needs attention.",
        overall_assessment="The observed risk is high but limited in scope.",
        plain_language_summary="One exposed service should be reviewed soon.",
        priority_actions=[
            AIRecommendedAction(
                priority="high",
                title="Review the affected service",
                description="Ask a qualified professional to validate the service.",
                related_finding_ids=[finding_id],
            )
        ],
        important_findings=[
            AIFindingExplanation(
                finding_id=finding_id,
                why_it_matters="The service is exposed and has a high risk score.",
                plain_language_explanation="An exposed service may need an update.",
                recommendation="Have a professional validate and update it.",
                evidence_used=["NVD validated the supplied CVE."],
                uncertainty=None,
            )
        ],
        uncertainties=[],
    )


def test_analyzer_accepts_structured_output_from_provider():
    context = _context()
    expected = _analysis(context.top_findings[0].finding_id)

    class FakeProvider:
        received = None

        def analyze_scan(self, supplied_context):
            self.received = supplied_context
            return expected

    provider = FakeProvider()
    result = generate_scan_analysis(provider, context)

    assert result == expected
    assert provider.received is context


@pytest.mark.parametrize("reference_location", ["explanation", "action"])
def test_analyzer_rejects_invented_finding_ids(reference_location):
    context = _context()
    analysis = _analysis(context.top_findings[0].finding_id)
    invented_id = uuid4()
    if reference_location == "explanation":
        analysis.important_findings[0].finding_id = invented_id
    else:
        analysis.priority_actions[0].related_finding_ids = [invented_id]

    class FakeProvider:
        def analyze_scan(self, supplied_context):
            return analysis

    with pytest.raises(AIAnalysisValidationError, match=str(invented_id)):
        generate_scan_analysis(FakeProvider(), context)


def test_analysis_schema_forbids_unknown_fields():
    context = _context()
    payload = _analysis(context.top_findings[0].finding_id).model_dump()
    payload["invented_score"] = 100

    with pytest.raises(ValidationError):
        ScanAIAnalysis.model_validate(payload)


def test_analyzer_rejects_duplicate_finding_explanations():
    context = _context()
    analysis = _analysis(context.top_findings[0].finding_id)
    analysis.important_findings.append(analysis.important_findings[0])

    class FakeProvider:
        def analyze_scan(self, supplied_context):
            return analysis

    with pytest.raises(AIAnalysisValidationError, match="duplicate"):
        generate_scan_analysis(FakeProvider(), context)
