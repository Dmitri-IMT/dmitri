from __future__ import annotations

import unicodedata

from api.schemas.ai import (
    AIFindingNote,
    AIFixTask,
    AIProviderFindingNote,
    AIProviderFixTask,
    AISourceLink,
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
    ScanAIAnalysis,
)
from api.services.ai.context import ScanAIContext

KEV_TASK_ERROR = "analysis omits a KEV finding from tasks"


class AIAnalysisValidationError(ValueError):
    pass


def validate_provider_analysis(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
) -> ProviderScanAIAnalysis:
    normalized = ProviderScanAIAnalysis(
        summary=_normalize_text(analysis.summary),
        tasks=[_normalized_task(task) for task in analysis.tasks],
        findings=[_normalized_note(note) for note in analysis.findings],
        not_checked=_optional_text(analysis.not_checked),
    )
    _require_kev_coverage(context, normalized)
    return normalized


def validate_provider_child_analysis(
    context: ScanAIContext,
    analysis: ProviderScanAIChildAnalysis,
) -> ProviderScanAIChildAnalysis:
    normalized = ProviderScanAIChildAnalysis(
        tasks=[_normalized_task(task) for task in analysis.tasks],
        findings=[_normalized_note(note) for note in analysis.findings],
    )
    _require_kev_coverage(context, normalized)
    return normalized


def sanitize_scan_ai_analysis(analysis: ScanAIAnalysis) -> ScanAIAnalysis:
    return ScanAIAnalysis(
        summary=_normalize_text(analysis.summary),
        tasks=[
            AIFixTask(
                rank=task.rank,
                priority=task.priority,
                title=_normalize_text(task.title),
                who=task.who,
                time=task.time,
                steps=[_normalize_text(step) for step in task.steps],
                fallback=_optional_text(task.fallback),
                fixes_fully=task.fixes_fully,
                finding_ids=task.finding_ids,
                highest_risk_score=task.highest_risk_score,
                sources=[
                    AISourceLink(name=_normalize_text(source.name), url=source.url)
                    for source in task.sources
                ],
            )
            for task in analysis.tasks
        ],
        findings=[
            AIFindingNote(
                finding_id=note.finding_id,
                plain_title=_normalize_text(note.plain_title),
                cause=_normalize_text(note.cause),
                what_could_happen=_normalize_text(note.what_could_happen),
                task_rank=note.task_rank,
            )
            for note in analysis.findings
        ],
        not_checked=_optional_text(analysis.not_checked),
    )


def _normalized_task(task: AIProviderFixTask) -> AIProviderFixTask:
    return AIProviderFixTask(
        title=_normalize_text(task.title),
        who=task.who,
        time=task.time,
        steps=[_normalize_text(step) for step in task.steps],
        fallback=_optional_text(task.fallback),
        fixes_fully=task.fixes_fully,
        fixes=list(dict.fromkeys(task.fixes)),
    )


def _normalized_note(note: AIProviderFindingNote) -> AIProviderFindingNote:
    return AIProviderFindingNote(
        finding_ref=note.finding_ref,
        plain_title=_normalize_text(note.plain_title),
        cause=_normalize_text(note.cause),
        what_could_happen=_normalize_text(note.what_could_happen),
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_text(value).strip() or None


def _require_kev_coverage(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis | ProviderScanAIChildAnalysis,
) -> None:
    kev_references = {
        finding.finding_ref for finding in context.top_findings if finding.is_kev
    }
    fixed_references = {
        reference for task in analysis.tasks for reference in task.fixes
    }
    if not kev_references <= fixed_references:
        raise AIAnalysisValidationError(KEV_TASK_ERROR)


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
