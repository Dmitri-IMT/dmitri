from __future__ import annotations

import pytest
from ai_shapes import provider_analysis, provider_task, stored_analysis
from api.schemas.read import (
    FindingEvidenceConfidenceCounts,
    FindingEvidenceMethodCounts,
    FindingEvidenceSummary,
    SeverityBreakdown,
)
from api.services.ai.context import AIFindingContext, ScanAIContext
from api.services.ai.validation import (
    KEV_TASK_ERROR,
    AIAnalysisValidationError,
    sanitize_scan_ai_analysis,
    validate_provider_analysis,
)


def _context() -> ScanAIContext:
    return ScanAIContext(
        scan_mode="quick",
        duration_seconds=1,
        host_count=1,
        total_findings=2,
        scored_findings=2,
        confirmed_findings=2,
        kev_findings=1,
        average_risk_score=55,
        max_risk_score=90,
        severity=SeverityBreakdown(),
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
        top_findings=[
            AIFindingContext(
                finding_ref="finding_1",
                machine_ref="machine_1",
                cve_id="CVE-2026-0001",
                cvss_score=9.8,
                severity="critical",
                confidence="confirmed",
                risk_score=90,
                exploitability=1,
                epss_score=0.9,
                epss_percentile=0.99,
                is_kev=True,
                known_ransomware=False,
            ),
            AIFindingContext(
                finding_ref="finding_2",
                machine_ref="machine_1",
                cve_id=None,
                cvss_score=5,
                severity="medium",
                confidence="confirmed",
                risk_score=20,
                exploitability=0.1,
                epss_score=None,
                epss_percentile=None,
                is_kev=False,
                known_ransomware=False,
            ),
        ],
    )


def test_validation_keeps_tasks_and_dedupes_their_references():
    analysis = provider_analysis(
        tasks=[
            provider_task("finding_2", "finding_2"),
            provider_task("finding_1"),
        ],
        findings=[],
    )

    validated = validate_provider_analysis(_context(), analysis)

    assert [task.fixes for task in validated.tasks] == [["finding_2"], ["finding_1"]]


def test_validation_rejects_missing_kev_task():
    analysis = provider_analysis(tasks=[provider_task("finding_2")], findings=[])

    with pytest.raises(AIAnalysisValidationError) as captured:
        validate_provider_analysis(_context(), analysis)

    assert str(captured.value) == KEV_TASK_ERROR


def test_validation_strips_invisible_unicode_before_persistence():
    analysis = provider_analysis(
        tasks=[
            provider_task(
                "finding_1",
                title="Update\u200b the router",
                steps=("Install\u2060 the update.",),
            )
        ],
        findings=[],
    )

    validated = validate_provider_analysis(_context(), analysis)

    assert validated.tasks[0].title == "Update the router"
    assert validated.tasks[0].steps == ["Install the update."]


def test_read_sanitizes_stored_analysis_before_rendering():
    analysis = stored_analysis()
    analysis.summary = "Resumo\u200b seguro."
    analysis.tasks[0].title = "Ação\ufe0f local"

    sanitized = sanitize_scan_ai_analysis(analysis)

    assert sanitized.summary == "Resumo seguro."
    assert sanitized.tasks[0].title == "Ação local"
