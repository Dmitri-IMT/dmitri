from __future__ import annotations

from uuid import uuid4

import pytest
from api.schemas.ai import (
    AIProviderRecommendedAction,
    AIRecommendedAction,
    ProviderScanAIAnalysis,
    ScanAIAnalysis,
)
from api.schemas.read import SeverityBreakdown
from api.services.ai.context import AIFindingContext, ScanAIContext
from api.services.ai.validation import (
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


def _analysis(actions: list[AIProviderRecommendedAction]) -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        executive_summary="Resumo seguro.",
        overall_assessment="Avaliação baseada nos fatos fornecidos.",
        plain_language_summary="Há pontos para revisar.",
        priority_actions=actions,
        important_findings=[],
        uncertainties=[],
    )


def test_validation_derives_priority_and_sorts_actions():
    analysis = _analysis(
        [
            AIProviderRecommendedAction(
                priority="immediate",
                title="Ação menos urgente",
                description="Revise o item de menor risco.",
                related_finding_refs=["finding_2"],
            ),
            AIProviderRecommendedAction(
                priority="low",
                title="Ação KEV",
                description="Revise o item listado no KEV.",
                related_finding_refs=["finding_1"],
            ),
        ]
    )

    validated = validate_provider_analysis(_context(), analysis)

    assert [action.priority for action in validated.priority_actions] == [
        "immediate",
        "low",
    ]
    assert validated.priority_actions[0].related_finding_refs == ["finding_1"]


def test_validation_rejects_missing_kev_action():
    analysis = _analysis(
        [
            AIProviderRecommendedAction(
                priority="high",
                title="Ação parcial",
                description="Revise apenas o segundo achado.",
                related_finding_refs=["finding_2"],
            )
        ]
    )

    with pytest.raises(AIAnalysisValidationError):
        validate_provider_analysis(_context(), analysis)


def test_validation_strips_invisible_unicode_before_persistence():
    analysis = _analysis(
        [
            AIProviderRecommendedAction(
                priority="low",
                title="Ação\u200b KEV",
                description="Revise\u2060 o item listado no KEV.",
                related_finding_refs=["finding_1"],
            )
        ]
    )

    validated = validate_provider_analysis(_context(), analysis)

    assert validated.priority_actions[0].title == "Ação KEV"
    assert validated.priority_actions[0].description == "Revise o item listado no KEV."


def test_read_sanitizes_legacy_analysis_before_rendering():
    analysis = ScanAIAnalysis(
        executive_summary="Resumo\u200b seguro.",
        overall_assessment="Avaliação segura.",
        plain_language_summary="Texto seguro.",
        priority_actions=[
            AIRecommendedAction(
                priority="low",
                title="Ação\ufe0f local",
                description="Descrição local segura.",
                related_finding_ids=[uuid4()],
            )
        ],
        important_findings=[],
        uncertainties=[],
    )

    sanitized = sanitize_scan_ai_analysis(analysis)

    assert sanitized.executive_summary == "Resumo seguro."
    assert sanitized.priority_actions[0].title == "Ação local"
