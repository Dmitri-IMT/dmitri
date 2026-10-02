from __future__ import annotations

from collections.abc import Iterable

from agent.normalize.contracts import CoverageObservationPayload, CoverageUnitPayload
from agent.scanner.models import HostInfo
from agent.targeted.models import (
    TargetedGapReason,
    TargetedObservation,
    TargetedUnitResult,
)
from agent.targeted.report import sanitize_evidence


def extract_coverage(hosts: Iterable[HostInfo]) -> list[CoverageUnitPayload]:
    coverage: list[CoverageUnitPayload] = []
    for host in hosts:
        coverage.extend(
            CoverageUnitPayload(
                ip=host.ip,
                stage=record.stage,
                outcome=record.outcome,
                reason_code=record.reason_code,
                evidence_source=record.evidence_source,
            )
            for record in host.stage_coverage
        )
        coverage.extend(_targeted_unit(result) for result in host.targeted_results)
    return coverage


_NOT_RUN_REASONS = {TargetedGapReason.SCAN_CANCELLED, TargetedGapReason.SCAN_TIMEOUT}


def _targeted_unit(result: TargetedUnitResult) -> CoverageUnitPayload:
    observations = [_observation(item) for item in result.observations]
    if result.reason_code in _NOT_RUN_REASONS:
        evidence_source = "not_run"
    elif result.outcome != "completed" and (result.issues or observations):
        evidence_source = "targeted_tool_partial_report"
    else:
        evidence_source = "targeted_tool"
    return CoverageUnitPayload(
        ip=result.unit.ip,
        stage="targeted_assessment",
        port=result.unit.port,
        protocol=result.unit.protocol,
        tool=result.unit.tool.value,
        outcome=result.outcome.value,
        reason_code=result.reason_code.value if result.reason_code else None,
        evidence_source=evidence_source,
        issue_keys=[issue.issue_key for issue in result.issues],
        observations=observations,
    )


def _observation(item: TargetedObservation) -> CoverageObservationPayload:
    return CoverageObservationPayload(
        observation_key=sanitize_evidence(item.observation_key, 512),
        kind=item.kind,
        summary=sanitize_evidence(item.summary, 512),
        evidence=sanitize_evidence(item.evidence, 512),
        path=sanitize_evidence(item.path, 256) if item.path else None,
        rule_id=sanitize_evidence(item.rule_id, 128) if item.rule_id else None,
        policy_version=(
            sanitize_evidence(item.policy_version, 64) if item.policy_version else None
        ),
    )
