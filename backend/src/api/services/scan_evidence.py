from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import TypeAdapter

from api.schemas.read import TargetedCoverageGap, TargetedToolCoverage
from api.schemas.scan import CoverageUnitPayload, EvidenceCompleteness

_CVE_CORRELATION_SOURCES = frozenset({"nmap_vulners", "nvd"})
_COVERAGE = TypeAdapter(list[CoverageUnitPayload])


def is_cve_correlation(cve_id: str | None, source: str | None) -> bool:
    return bool(cve_id) and source in _CVE_CORRELATION_SOURCES


def parse_coverage(raw: list[dict[str, Any]] | None) -> list[CoverageUnitPayload]:
    return _COVERAGE.validate_python(raw or [])


def parse_targeted_coverage(
    metadata: dict[str, Any] | None,
) -> list[TargetedToolCoverage]:
    raw = (metadata or {}).get("targeted_coverage")
    if not isinstance(raw, str):
        return []
    tools: list[TargetedToolCoverage] = []
    for chunk in raw.split(";"):
        tool, _, detail = chunk.partition(":")
        counts_text, _, gaps_text = detail.partition(",gaps=")
        counts = dict(item.partition("=")[::2] for item in counts_text.split(","))
        if not tool or not all(counts.get(key, "").isdigit() for key in "cfts"):
            continue
        gaps = []
        for gap in gaps_text.split("|") if gaps_text else []:
            reason, _, count = gap.partition(":")
            if reason and count.isdigit():
                gaps.append(TargetedCoverageGap(reason=reason, count=int(count)))
        tools.append(
            TargetedToolCoverage(
                tool=tool,
                completed=int(counts["c"]),
                failed=int(counts["f"]),
                timed_out=int(counts["t"]),
                skipped=int(counts["s"]),
                gaps=gaps,
            )
        )
    return tools


def incomplete_check_count(coverage: Sequence[CoverageUnitPayload]) -> int:
    return sum(unit.outcome != "completed" for unit in coverage)


def evidence_completeness(
    metadata: dict[str, Any] | None,
    coverage: Sequence[CoverageUnitPayload],
) -> EvidenceCompleteness:
    flag = (metadata or {}).get("partial_result")
    if flag is True or incomplete_check_count(coverage) > 0:
        return "partial"
    if flag is False:
        return "complete"
    return "unknown"
