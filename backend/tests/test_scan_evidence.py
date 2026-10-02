from __future__ import annotations

import pytest
from api.schemas.scan import CoverageUnitPayload
from api.services.scan_evidence import (
    evidence_completeness,
    incomplete_check_count,
    is_cve_correlation,
    parse_coverage,
)


def _unit(outcome: str) -> CoverageUnitPayload:
    return CoverageUnitPayload(
        ip="10.0.0.5",
        stage="ports",
        outcome=outcome,
        evidence_source="nmap_ports",
    )


@pytest.mark.parametrize(
    ("metadata", "coverage", "expected"),
    [
        ({"partial_result": False}, [], "complete"),
        ({"partial_result": False}, [_unit("completed")], "complete"),
        ({"partial_result": True}, [_unit("completed")], "partial"),
        ({"partial_result": False}, [_unit("timed_out")], "partial"),
        (None, [_unit("skipped")], "partial"),
        (None, [], "unknown"),
        ({"partial_result": "yes"}, [_unit("completed")], "unknown"),
    ],
)
def test_evidence_completeness(metadata, coverage, expected) -> None:
    assert evidence_completeness(metadata, coverage) == expected


def test_incomplete_check_count_counts_every_unfinished_outcome() -> None:
    coverage = [_unit(outcome) for outcome in ("completed", "partial", "skipped")]
    assert incomplete_check_count(coverage) == 2


def test_parse_coverage_reads_stored_json() -> None:
    stored = [_unit("failed").model_dump(mode="json")]
    assert parse_coverage(stored) == [_unit("failed")]
    assert parse_coverage(None) == []


@pytest.mark.parametrize(
    ("cve_id", "source", "expected"),
    [
        ("CVE-2026-0001", "nmap_vulners", True),
        ("CVE-2026-0001", "nvd", True),
        ("CVE-2026-0001", "targeted", False),
        (None, "nmap_vulners", False),
    ],
)
def test_is_cve_correlation(cve_id, source, expected) -> None:
    assert is_cve_correlation(cve_id, source) is expected
