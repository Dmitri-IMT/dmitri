from __future__ import annotations

from uuid import UUID

from api.services.ai.schemas import ScanAIAnalysis, ScanAIContext


class AIAnalysisValidationError(ValueError):
    """The provider referred to data outside the supplied scan context."""


def validate_scan_analysis(
    context: ScanAIContext,
    analysis: ScanAIAnalysis,
) -> None:
    allowed_ids = {finding.finding_id for finding in context.top_findings}
    explanation_ids = [item.finding_id for item in analysis.important_findings]
    referenced_ids: set[UUID] = set(explanation_ids)
    for action in analysis.priority_actions:
        referenced_ids.update(action.related_finding_ids)

    unknown_ids = referenced_ids - allowed_ids
    if unknown_ids:
        rendered = ", ".join(sorted(str(value) for value in unknown_ids))
        raise AIAnalysisValidationError(
            f"analysis references findings outside its context: {rendered}"
        )

    if len(explanation_ids) != len(set(explanation_ids)):
        raise AIAnalysisValidationError(
            "analysis contains duplicate finding explanations"
        )
