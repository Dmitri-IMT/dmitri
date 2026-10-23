from __future__ import annotations

import re
from collections.abc import Iterable

from api.schemas.ai import ProviderScanAIAnalysis, ProviderScanAIChildAnalysis

WRITING_SKILL_VERSION = "3"

_URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HTML_PATTERN = re.compile(r"<[/!]?[a-z][^>]*>", re.IGNORECASE)
_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC_PATTERN = re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.IGNORECASE)
_MARKDOWN_PATTERN = re.compile(r"(?:^|\s)(?:#{1,6}\s|[-*+]\s|`|\*\*)")
_CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]?", re.DOTALL)
_WORD_PATTERN = re.compile(r"[A-Za-z0-9_']+")

_BANNED_TERMS = (
    "additionally",
    "crucial",
    "delve",
    "enhance",
    "fostering",
    "garner",
    "interplay",
    "intricate",
    "landscape",
    "pivotal",
    "showcase",
    "tapestry",
    "testament",
    "underscore",
    "vibrant",
    "robust",
    "seamless",
    "comprehensive",
    "holistic",
    "leverage",
    "utilize",
    "empower",
    "navigate",
    "realm",
    "paramount",
    "security posture",
    "threat landscape",
    "bad actors",
    "cyber hygiene",
    "stay vigilant",
    "proactive measures",
    "best-in-class",
    "defense in depth",
    "peace of mind",
    "bulletproof",
    "military-grade",
    "hackers",
    "it is important to note",
    "it is worth noting",
    "please note",
    "in today's world",
    "at the end of the day",
    "it should be noted",
    "needless to say",
    "could potentially",
    "may possibly",
    "might perhaps",
    "catastrophic",
    "devastating",
    "alarming",
    "feel free",
    "hope this helps",
    "let me know",
    "great question",
    "certainly",
    "of course",
    "as an ai",
)
_RETIRED_WORDS = ("finding", "issue", "weakness", "device", "host", "endpoint", "asset")
_SAFETY_PATTERN = re.compile(
    r"\b(?:network|machine_\d+|service)\s+(?:is|are)\s+"
    r"(?:safe|secure|protected|clean)\b",
    re.IGNORECASE,
)


class WritingStyleViolation(ValueError):
    def __init__(self, codes: Iterable[str]) -> None:
        self.codes = tuple(sorted(set(codes)))
        super().__init__("style_violation")


def lint_provider_analysis(analysis: ProviderScanAIAnalysis) -> None:
    _lint_prose(analysis)


def lint_provider_child_analysis(analysis: ProviderScanAIChildAnalysis) -> None:
    _lint_prose(analysis)


def _lint_prose(
    analysis: ProviderScanAIAnalysis | ProviderScanAIChildAnalysis,
) -> None:
    violations: list[str] = []
    for field, value, limit in _prose_fields(analysis):
        if len(value) > limit:
            violations.append(f"{field}:too_long")
        violations.extend(_text_violations(field, value))
    if violations:
        raise WritingStyleViolation(violations)


def _prose_fields(
    analysis: ProviderScanAIAnalysis | ProviderScanAIChildAnalysis,
) -> list[tuple[str, str, int]]:
    values: list[tuple[str, str, int]] = []
    if isinstance(analysis, ProviderScanAIAnalysis):
        values.append(("summary", analysis.summary, 280))
        if analysis.not_checked is not None:
            values.append(("not_checked", analysis.not_checked, 200))
    for index, task in enumerate(analysis.tasks):
        values.append((f"tasks[{index}].title", task.title, 60))
        values.extend(
            (f"tasks[{index}].steps[{step_index}]", step, 160)
            for step_index, step in enumerate(task.steps)
        )
        if task.fallback is not None:
            values.append((f"tasks[{index}].fallback", task.fallback, 160))
    for index, note in enumerate(analysis.findings):
        values.extend(
            [
                (f"findings[{index}].plain_title", note.plain_title, 90),
                (f"findings[{index}].cause", note.cause, 160),
                (f"findings[{index}].what_could_happen", note.what_could_happen, 160),
            ]
        )
    return values


def _text_violations(field: str, value: str) -> list[str]:
    lowered = value.lower()
    violations = []
    if (
        _URL_PATTERN.search(value)
        or _HTML_PATTERN.search(value)
        or _MARKDOWN_PATTERN.search(value)
    ):
        violations.append(f"{field}:markup")
    if (
        _IP_PATTERN.search(value)
        or _MAC_PATTERN.search(value)
        or _CVE_PATTERN.search(value)
    ):
        violations.append(f"{field}:raw_identifier")
    if _SAFETY_PATTERN.search(value):
        violations.append(f"{field}:safety_certification")
    if any(_contains_term(lowered, term) for term in _RETIRED_WORDS):
        violations.append(f"{field}:retired_vocabulary")
    if any(_contains_term(lowered, term) for term in _BANNED_TERMS):
        violations.append(f"{field}:banned_pattern")
    if any(punctuation in value for punctuation in ("—", "–", ";", "!", "(", ")")):
        violations.append(f"{field}:punctuation")
    if any(
        len(_WORD_PATTERN.findall(sentence)) > 25
        for sentence in _SENTENCE_PATTERN.findall(value)
    ):
        violations.append(f"{field}:sentence_too_long")
    return violations


def _contains_term(value: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", value) is not None
