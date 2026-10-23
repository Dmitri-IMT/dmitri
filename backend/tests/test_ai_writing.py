from __future__ import annotations

import pytest
from ai_shapes import provider_analysis, provider_task
from api.services.ai.writing import WritingStyleViolation, lint_provider_analysis


def test_linter_accepts_plain_grounded_prose():
    lint_provider_analysis(provider_analysis())


@pytest.mark.parametrize(
    ("summary", "expected_code"),
    [
        ("Your network is safe.", "summary:safety_certification"),
        ("Review 192.168.1.10 for this vulnerability.", "summary:raw_identifier"),
        (
            "It is crucial to enhance your security posture.",
            "summary:banned_pattern",
        ),
        ("A device needs attention.", "summary:retired_vocabulary"),
        ("Read [this guide](https://example.test).", "summary:markup"),
        (
            "This sentence has many words and keeps adding details so that it exceeds "
            "the allowed number of words for one sentence now without any useful "
            "reason at all today.",
            "summary:sentence_too_long",
        ),
    ],
)
def test_linter_rejects_unsafe_or_unclear_prose(summary, expected_code):
    with pytest.raises(WritingStyleViolation) as captured:
        lint_provider_analysis(provider_analysis(summary=summary))

    assert expected_code in captured.value.codes


def test_linter_checks_every_task_step_and_title_length():
    analysis = provider_analysis(
        tasks=[
            provider_task(
                title="Update the software on machine_1 and every other machine today",
                steps=("Install it (see the vendor page).",),
            )
        ]
    )

    with pytest.raises(WritingStyleViolation) as captured:
        lint_provider_analysis(analysis)

    assert "tasks[0].title:too_long" in captured.value.codes
    assert "tasks[0].steps[0]:punctuation" in captured.value.codes
