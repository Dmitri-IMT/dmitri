from __future__ import annotations

from uuid import uuid4

from api.schemas.ai import (
    AIProviderFindingExplanation,
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
)
from api.schemas.read import (
    FindingEvidenceConfidenceCounts,
    FindingEvidenceMethodCounts,
    FindingEvidenceSummary,
    SeverityBreakdown,
)
from api.services.ai.analyzer import run_bounded_analysis, split_context
from api.services.ai.context import AIFindingContext, ScanAIContext
from api.services.ai.groq import AIProviderError


def _context() -> ScanAIContext:
    findings = [
        AIFindingContext(
            finding_ref=f"finding_{index}",
            machine_ref=None,
            cve_id=None,
            cvss_score=None,
            severity="medium",
            confidence=None,
            risk_score=40,
            exploitability=None,
            epss_score=None,
            epss_percentile=None,
            is_kev=False,
            known_ransomware=False,
        )
        for index in (1, 2)
    ]
    context = ScanAIContext(
        scan_mode="quick",
        duration_seconds=10,
        host_count=1,
        total_findings=2,
        scored_findings=2,
        confirmed_findings=0,
        kev_findings=0,
        average_risk_score=40,
        max_risk_score=40,
        severity=SeverityBreakdown(medium=2),
        top_findings=findings,
        evidence_summary=FindingEvidenceSummary(
            scope="scan",
            total_records=0,
            by_method=FindingEvidenceMethodCounts(
                version_correlation=0,
                configuration_observation=0,
                specific_check=0,
                textual_reference=0,
                unknown=0,
            ),
            by_confidence=FindingEvidenceConfidenceCounts(
                tentative=0, probable=0, confirmed=0, unknown=0
            ),
            conflicting_records=0,
            demonstrated_records=0,
        ),
    )
    context._finding_ids_by_ref = {
        "finding_1": uuid4(),
        "finding_2": uuid4(),
    }
    context._display_values_by_ref = {
        "finding_1": "finding_1",
        "finding_2": "finding_2",
    }
    return context


def _child(ref: str) -> ProviderScanAIChildAnalysis:
    return ProviderScanAIChildAnalysis(
        priority_actions=[],
        important_findings=[
            AIProviderFindingExplanation(
                finding_ref=ref,
                why_it_matters="This vulnerability needs review.",
                plain_language_explanation="An exposed service needs review.",
                recommendation="Ask an IT professional to review it.",
                evidence_used=["The scan recorded this vulnerability."],
                uncertainty=None,
            )
        ],
        uncertainties=[],
    )


def _synthesis() -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        executive_summary="Two vulnerabilities need attention.",
        overall_assessment="The observed risk is limited in scope.",
        plain_language_summary="Ask an IT professional to review the results.",
        priority_actions=[],
        important_findings=[],
        uncertainties=[
            "The scan cannot confirm whether the vulnerabilities were used."
        ],
    )


def test_split_context_preserves_private_reference_maps():
    context = _context()
    context.evidence_completeness = "partial"
    context.stopped_by = "timeout"
    context.industrial_protocols.opcua_tcp.service_count = 2
    context.industrial_protocols.opcua_tcp.confirmed_services = 1
    context.industrial_protocols.opcua_tcp.mapping_limited = 1
    context.industrial_protocols.opcua_tcp.anonymous_read_verified = 1
    chunks = split_context(context, child_findings=1)

    assert [len(chunk.top_findings) for chunk in chunks] == [1, 1]
    assert set(chunks[0]._finding_ids_by_ref) == {"finding_1"}
    assert set(chunks[1]._finding_ids_by_ref) == {"finding_2"}
    assert all(chunk.evidence_completeness == "partial" for chunk in chunks)
    assert all(chunk.stopped_by == "timeout" for chunk in chunks)
    assert all(
        chunk.industrial_protocols == context.industrial_protocols
        for chunk in chunks
    )


class _BoundedProvider:
    """Satisfies BoundedScanAnalysisProvider; subclasses override what they exercise."""

    def analyze_scan(self, context, *, language="en"):
        raise AssertionError("the bounded pipeline must not call analyze_scan")

    def repair_analysis(self, context, violation_codes, *, language="en"):
        raise AssertionError("no final repair was expected")

    def analyze_chunk(self, context, *, language="en"):
        raise NotImplementedError

    def repair_chunk(self, context, violation_codes, *, language="en"):
        raise AssertionError("no writing violation was expected")

    def synthesize_scan(self, context, child_results, failed_refs, *, language="en"):
        raise NotImplementedError


def test_bounded_pipeline_synthesizes_validated_children():
    received = []

    class Provider(_BoundedProvider):
        def analyze_chunk(self, context, *, language="en"):
            received.append(context.top_findings[0].finding_ref)
            return _child(context.top_findings[0].finding_ref)

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            assert len(child_results) == 2
            assert failed_refs == ()
            return _synthesis()

    analysis, coverage = run_bounded_analysis(Provider(), _context(), child_findings=1)

    assert analysis == _synthesis()
    assert received == ["finding_1", "finding_2"]
    assert coverage.analyzed_findings == 2
    assert coverage.failed_findings == 0
    assert coverage.total_findings == 2


def test_child_failure_is_reported_to_synthesizer():
    captured = {}

    class Provider(_BoundedProvider):
        def analyze_chunk(self, context, *, language="en"):
            if context.top_findings[0].finding_ref == "finding_1":
                raise AIProviderError("provider_timeout", retryable=True)
            return _child("finding_2")

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            captured["children"] = child_results
            captured["failed"] = failed_refs
            return _synthesis()

    _, coverage = run_bounded_analysis(Provider(), _context(), child_findings=1)

    assert len(captured["children"]) == 1
    assert captured["failed"] == ("finding_1",)
    assert coverage.analyzed_findings == 1
    assert coverage.failed_findings == 1


def test_bounded_child_and_repair_keep_partial_coverage():
    context = _context()
    context.evidence_completeness = "partial"
    context.stopped_by = "error"
    received = {"child": [], "repair": []}

    class Provider(_BoundedProvider):
        def analyze_chunk(self, chunk, *, language="en"):
            received["child"].append((chunk.evidence_completeness, chunk.stopped_by))
            child = _child(chunk.top_findings[0].finding_ref)
            child.important_findings[0].why_it_matters = "The device needs review."
            return child

        def repair_chunk(self, chunk, violation_codes, *, language="en"):
            received["repair"].append((chunk.evidence_completeness, chunk.stopped_by))
            return _child(chunk.top_findings[0].finding_ref)

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            return _synthesis()

    _, coverage = run_bounded_analysis(Provider(), context, child_findings=1)

    assert coverage.analyzed_findings == 2
    assert received["child"] == [("partial", "error"), ("partial", "error")]
    assert received["repair"] == [("partial", "error"), ("partial", "error")]


def test_invalid_child_reference_is_repaired_inside_analyzer():
    received = []

    class Provider(_BoundedProvider):
        def analyze_chunk(self, context, *, language="en"):
            return _child("finding_99")

        def repair_chunk(self, context, violation_codes, *, language="en"):
            received.append(violation_codes)
            return _child(context.top_findings[0].finding_ref)

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            assert len(child_results) == 2
            assert failed_refs == ()
            return _synthesis()

    _, coverage = run_bounded_analysis(Provider(), _context(), child_findings=1)
    assert received == [("analysis contains an unknown reference",)] * 2
    assert coverage.analyzed_findings == 2
    assert coverage.failed_findings == 0


def test_synthesis_style_repair_stays_inside_analyzer():
    calls = []

    class Provider(_BoundedProvider):
        def analyze_chunk(self, context, *, language="en"):
            return _child(context.top_findings[0].finding_ref)

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            analysis = _synthesis()
            analysis.executive_summary = "Your network is safe."
            return analysis

        def repair_analysis(self, context, violation_codes, *, language="en"):
            calls.append((violation_codes, language))
            return _synthesis()

    analysis, coverage = run_bounded_analysis(
        Provider(), _context(), child_findings=1, language="pt-BR"
    )
    assert analysis == _synthesis()
    assert calls == [(("executive_summary:safety_certification",), "pt-BR")]
    assert coverage.analyzed_findings == 2
