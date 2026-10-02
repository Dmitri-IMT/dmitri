from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import TypeAdapter

from api.schemas.scan import CoverageUnitPayload

EvidenceCompleteness = Literal["complete", "partial", "unknown"]

_CVE_CORRELATION_SOURCES = frozenset({"nmap_vulners", "nvd"})
_COVERAGE = TypeAdapter(list[CoverageUnitPayload])


def is_cve_correlation(cve_id: str | None, source: str | None) -> bool:
    return bool(cve_id) and source in _CVE_CORRELATION_SOURCES


def parse_coverage(raw: list[dict[str, Any]] | None) -> list[CoverageUnitPayload]:
    return _COVERAGE.validate_python(raw or [])


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
