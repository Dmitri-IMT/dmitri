from __future__ import annotations

from dataclasses import dataclass

from api.schemas.ai import (
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
)
from api.services.ai.context import ScanAIContext
from api.services.ai.groq import AIProviderError
from api.services.ai.providers import (
    BoundedScanAnalysisProvider,
    ScanAnalysisProvider,
    supports_bounded_scan_analysis,
)
from api.services.ai.validation import (
    AIAnalysisValidationError,
    validate_provider_analysis,
    validate_provider_child_analysis,
)
from api.services.ai.writing import (
    WritingStyleViolation,
    lint_provider_analysis,
    lint_provider_child_analysis,
)

DEFAULT_CHILD_FINDINGS = 5


@dataclass(frozen=True)
class AnalysisCoverage:
    analyzed_findings: int
    failed_findings: int
    total_findings: int


def run_bounded_analysis(
    provider: ScanAnalysisProvider,
    context: ScanAIContext,
    *,
    child_findings: int = DEFAULT_CHILD_FINDINGS,
    language: str = "en",
) -> tuple[ProviderScanAIAnalysis, AnalysisCoverage]:
    """Run isolated finding chunks, then synthesize only validated child output."""
    if child_findings < 1:
        raise ValueError("child_findings must be positive")
    if not supports_bounded_scan_analysis(provider):
        analysis = provider.analyze_scan(context, language=language)
        return validate_analysis_with_repair(
            provider, context, analysis, language=language
        ), AnalysisCoverage(
            analyzed_findings=len(context.top_findings),
            failed_findings=0,
            total_findings=len(context.top_findings),
        )

    chunks = split_context(context, child_findings)
    children: list[dict[str, object]] = []
    failed_refs: list[str] = []
    analyzed = 0
    for chunk in chunks:
        refs = [finding.finding_ref for finding in chunk.top_findings]
        try:
            child = _run_child(provider, chunk, language=language)
        except AIProviderError as exc:
            if exc.code == "provider_rate_limited":
                raise
            failed_refs.extend(refs)
            continue
        except (WritingStyleViolation, ValueError):
            failed_refs.extend(refs)
            continue
        children.append(child.model_dump(mode="json"))
        analyzed += len(refs)

    synthesis = provider.synthesize_scan(
        context, children, tuple(failed_refs), language=language
    )
    return validate_analysis_with_repair(
        provider, context, synthesis, language=language
    ), AnalysisCoverage(
        analyzed_findings=analyzed,
        failed_findings=len(failed_refs),
        total_findings=len(context.top_findings),
    )


def split_context(
    context: ScanAIContext,
    child_findings: int = DEFAULT_CHILD_FINDINGS,
) -> list[ScanAIContext]:
    chunks: list[ScanAIContext] = []
    findings = context.top_findings
    for start in range(0, len(findings), child_findings):
        selected = findings[start : start + child_findings]
        chunk = ScanAIContext(
            scan_mode=context.scan_mode,
            evidence_completeness=context.evidence_completeness,
            incomplete_check_count=context.incomplete_check_count,
            duration_seconds=context.duration_seconds,
            stopped_by=context.stopped_by,
            host_count=context.host_count,
            total_findings=context.total_findings,
            scored_findings=context.scored_findings,
            confirmed_findings=context.confirmed_findings,
            kev_findings=context.kev_findings,
            average_risk_score=context.average_risk_score,
            max_risk_score=context.max_risk_score,
            severity=context.severity,
            top_findings=selected,
            evidence_summary=context.evidence_summary,
        )
        chunk._finding_ids_by_ref = {
            finding.finding_ref: context._finding_ids_by_ref[finding.finding_ref]
            for finding in selected
        }
        chunk._display_values_by_ref = {
            finding.finding_ref: context._display_values_by_ref[finding.finding_ref]
            for finding in selected
        }
        chunks.append(chunk)
    return chunks


def _run_child(
    provider: BoundedScanAnalysisProvider,
    context: ScanAIContext,
    *,
    language: str,
) -> ProviderScanAIChildAnalysis:
    child = provider.analyze_chunk(context, language=language)
    if not isinstance(child, ProviderScanAIChildAnalysis):
        child = ProviderScanAIChildAnalysis.model_validate(child)
    try:
        child = validate_provider_child_analysis(context, child)
        _validate_references(context, child)
        lint_provider_child_analysis(child)
    except (WritingStyleViolation, AIAnalysisValidationError) as exc:
        codes = exc.codes if isinstance(exc, WritingStyleViolation) else (str(exc),)
        child = provider.repair_chunk(context, codes, language=language)
        if not isinstance(child, ProviderScanAIChildAnalysis):
            child = ProviderScanAIChildAnalysis.model_validate(child)
        child = validate_provider_child_analysis(context, child)
        lint_provider_child_analysis(child)
    _validate_references(context, child)
    return child


def validate_analysis_with_repair(
    provider: ScanAnalysisProvider,
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
    *,
    language: str,
) -> ProviderScanAIAnalysis:
    """Repair an invalid provider result once, then accept it or fail."""
    try:
        return _validate_analysis(context, analysis)
    except (AIAnalysisValidationError, WritingStyleViolation) as exc:
        codes = exc.codes if isinstance(exc, WritingStyleViolation) else (str(exc),)
        repaired = provider.repair_analysis(context, codes, language=language)
        return _validate_analysis(context, repaired)


def _validate_analysis(
    context: ScanAIContext, analysis: ProviderScanAIAnalysis,
) -> ProviderScanAIAnalysis:
    normalized = validate_provider_analysis(context, analysis)
    _validate_references(context, normalized)
    lint_provider_analysis(normalized)
    return normalized


def _validate_references(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis | ProviderScanAIChildAnalysis,
) -> None:
    allowed = {finding.finding_ref for finding in context.top_findings}
    explained = [item.finding_ref for item in analysis.important_findings]
    referenced = set(explained).union(
        *(action.related_finding_refs for action in analysis.priority_actions)
    )
    if not referenced <= allowed:
        raise AIAnalysisValidationError("analysis contains an unknown reference")
    if len(explained) != len(set(explained)):
        raise AIAnalysisValidationError(
            "analysis contains duplicate finding references"
        )
