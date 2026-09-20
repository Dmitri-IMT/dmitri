from __future__ import annotations

import pytest
from api.schemas.ai import AIProviderRecommendedAction, ProviderScanAIAnalysis
from api.services.ai.writing import WritingStyleViolation, lint_provider_analysis


def _analysis(
    *, summary: str = "One vulnerability needs attention."
) -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        executive_summary=summary,
        overall_assessment="The exposed service needs a review by an IT professional.",
        plain_language_summary="Ask an IT professional to review this vulnerability.",
        priority_actions=[
            AIProviderRecommendedAction(
                priority="high",
                title="Review machine_1",
                description="Ask the IT professional to review machine_1 this week.",
                related_finding_refs=["finding_1"],
            )
        ],
        important_findings=[],
        uncertainties=["This scan cannot confirm whether the vulnerability was used."],
    )


def test_linter_accepts_plain_grounded_prose():
    lint_provider_analysis(_analysis())


@pytest.mark.parametrize(
    ("summary", "expected_code"),
    [
        ("Your network is safe.", "executive_summary:safety_certification"),
        (
            "Review 192.168.1.10 for this vulnerability.",
            "executive_summary:raw_identifier",
        ),
        (
            "It is crucial to enhance your security posture.",
            "executive_summary:banned_pattern",
        ),
        ("A device needs attention.", "executive_summary:retired_vocabulary"),
        ("Read [this guide](https://example.test).", "executive_summary:markup"),
        (
            "This sentence has many words and keeps adding details so that it exceeds "
            "the allowed number of words for one sentence now without any useful "
            "reason at all today.",
            "executive_summary:sentence_too_long",
        ),
    ],
)
def test_linter_rejects_unsafe_or_unclear_prose(summary, expected_code):
    with pytest.raises(WritingStyleViolation) as captured:
        lint_provider_analysis(_analysis(summary=summary))

    assert expected_code in captured.value.codes


def test_linter_rejects_too_many_limitations():
    analysis = _analysis()
    analysis.uncertainties = [
        "This scan cannot confirm one fact.",
        "This scan cannot confirm two facts.",
        "This scan cannot confirm three facts.",
        "This scan cannot confirm four facts.",
    ]

    with pytest.raises(WritingStyleViolation) as captured:
        lint_provider_analysis(analysis)

    assert "uncertainties:too_many" in captured.value.codes
