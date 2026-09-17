from __future__ import annotations

import unicodedata

from api.schemas.ai import (
    AIFindingExplanation,
    AIProviderFindingExplanation,
    AIProviderRecommendedAction,
    AIRecommendedAction,
    ProviderScanAIAnalysis,
    ScanAIAnalysis,
)
from api.services.ai.context import AIFindingContext, ScanAIContext

_PRIORITY_ORDER = {"immediate": 0, "high": 1, "medium": 2, "low": 3}


class AIAnalysisValidationError(ValueError):
    pass


def validate_provider_analysis(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
) -> ProviderScanAIAnalysis:
    normalized = ProviderScanAIAnalysis(
        executive_summary=_normalize_text(analysis.executive_summary),
        overall_assessment=_normalize_text(analysis.overall_assessment),
        plain_language_summary=_normalize_text(analysis.plain_language_summary),
        priority_actions=[
            AIProviderRecommendedAction(
                priority=_priority_for_references(
                    context, action.related_finding_refs
                ),
                title=_normalize_text(action.title),
                description=_normalize_text(action.description),
                related_finding_refs=action.related_finding_refs,
            )
            for action in analysis.priority_actions
        ],
        important_findings=[
            AIProviderFindingExplanation(
                finding_ref=item.finding_ref,
                why_it_matters=_normalize_text(item.why_it_matters),
                plain_language_explanation=_normalize_text(
                    item.plain_language_explanation
                ),
                recommendation=_normalize_text(item.recommendation),
                evidence_used=[_normalize_text(value) for value in item.evidence_used],
                uncertainty=(
                    _normalize_text(item.uncertainty)
                    if item.uncertainty is not None
                    else None
                ),
            )
            for item in analysis.important_findings
        ],
        uncertainties=[_normalize_text(value) for value in analysis.uncertainties],
    )
    _require_kev_coverage(context, normalized)
    normalized.priority_actions.sort(
        key=lambda action: _PRIORITY_ORDER[action.priority]
    )
    return normalized


def sanitize_scan_ai_analysis(analysis: ScanAIAnalysis) -> ScanAIAnalysis:
    return ScanAIAnalysis(
        executive_summary=_normalize_text(analysis.executive_summary),
        overall_assessment=_normalize_text(analysis.overall_assessment),
        plain_language_summary=_normalize_text(analysis.plain_language_summary),
        priority_actions=[
            AIRecommendedAction(
                priority=action.priority,
                title=_normalize_text(action.title),
                description=_normalize_text(action.description),
                related_finding_ids=action.related_finding_ids,
            )
            for action in analysis.priority_actions
        ],
        important_findings=[
            AIFindingExplanation(
                finding_id=item.finding_id,
                why_it_matters=_normalize_text(item.why_it_matters),
                plain_language_explanation=_normalize_text(
                    item.plain_language_explanation
                ),
                recommendation=_normalize_text(item.recommendation),
                evidence_used=[_normalize_text(value) for value in item.evidence_used],
                uncertainty=(
                    _normalize_text(item.uncertainty)
                    if item.uncertainty is not None
                    else None
                ),
            )
            for item in analysis.important_findings
        ],
        uncertainties=[_normalize_text(value) for value in analysis.uncertainties],
    )


def _require_kev_coverage(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
) -> None:
    kev_references = {
        finding.finding_ref for finding in context.top_findings if finding.is_kev
    }
    action_references = {
        reference
        for action in analysis.priority_actions
        for reference in action.related_finding_refs
    }
    if not kev_references <= action_references:
        raise AIAnalysisValidationError("analysis omits a KEV finding from actions")


def _priority_for_references(
    context: ScanAIContext,
    references: list[str],
) -> str:
    findings_by_reference = {
        finding.finding_ref: finding for finding in context.top_findings
    }
    priorities = [
        _priority_for_finding(findings_by_reference[reference])
        for reference in references
        if reference in findings_by_reference
    ]
    return min(priorities, key=_PRIORITY_ORDER.__getitem__, default="low")


def _priority_for_finding(finding: AIFindingContext) -> str:
    if finding.is_kev:
        return "immediate"
    if (
        (finding.risk_score is not None and finding.risk_score >= 70)
        or (finding.cvss_score is not None and finding.cvss_score >= 9)
        or (finding.epss_score is not None and finding.epss_score >= 0.7)
    ):
        return "high"
    if (
        (finding.risk_score is not None and finding.risk_score >= 40)
        or (finding.cvss_score is not None and finding.cvss_score >= 7)
    ):
        return "medium"
    return "low"


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        character for character in normalized if not _is_invisible(character)
    )


def _is_invisible(character: str) -> bool:
    codepoint = ord(character)
    return (
        unicodedata.category(character) == "Cf"
        or 0xFE00 <= codepoint <= 0xFE0F
        or 0xE0000 <= codepoint <= 0xE007F
    )
