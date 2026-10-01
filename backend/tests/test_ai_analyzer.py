from __future__ import annotations

from uuid import uuid4

from api.schemas.ai import (
    AIProviderFindingExplanation,
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
)
from api.schemas.read import SeverityBreakdown
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
    context.partial_result = True
    context.stopped_by = "timeout"
    chunks = split_context(context, child_findings=1)

    assert [len(chunk.top_findings) for chunk in chunks] == [1, 1]
    assert set(chunks[0]._finding_ids_by_ref) == {"finding_1"}
    assert set(chunks[1]._finding_ids_by_ref) == {"finding_2"}
    assert all(chunk.partial_result is True for chunk in chunks)
    assert all(chunk.stopped_by == "timeout" for chunk in chunks)


class _BoundedProvider:
    """Satisfies BoundedScanAnalysisProvider; subclasses override what they exercise."""

    def analyze_scan(self, context, *, language="en"):
        raise AssertionError("the bounded pipeline must not call analyze_scan")

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
    context.partial_result = True
    context.stopped_by = "error"
    received = {"child": [], "repair": []}

    class Provider(_BoundedProvider):
        def analyze_chunk(self, chunk, *, language="en"):
            received["child"].append((chunk.partial_result, chunk.stopped_by))
            child = _child(chunk.top_findings[0].finding_ref)
            child.important_findings[0].why_it_matters = "The device needs review."
            return child

        def repair_chunk(self, chunk, violation_codes, *, language="en"):
            received["repair"].append((chunk.partial_result, chunk.stopped_by))
            return _child(chunk.top_findings[0].finding_ref)

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            return _synthesis()

    _, coverage = run_bounded_analysis(Provider(), context, child_findings=1)

    assert coverage.analyzed_findings == 2
    assert received["child"] == [(True, "error"), (True, "error")]
    assert received["repair"] == [(True, "error"), (True, "error")]
