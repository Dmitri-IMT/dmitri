"""Internal models for bounded service-targeted assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class TargetedTool(StrEnum):
    """Supported targeted tools in their stable execution order."""

    FFUF = "ffuf"
    NIKTO = "nikto"
    TESTSSL = "testssl.sh"
    ENUM4LINUX = "enum4linux-ng"
    SSH_AUDIT = "ssh-audit"
    FTP_CHECK = "ftp-check"
    TELNET_CHECK = "telnet-check"


class TargetedOutcome(StrEnum):
    """Terminal outcome for one targeted unit."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


class TargetedGapReason(StrEnum):
    """Stable coverage-gap reason codes in metadata order."""

    TOOL_UNAVAILABLE = "tool_unavailable"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INCOMPATIBLE_TOOL = "incompatible_tool"
    WORDLIST_UNAVAILABLE = "wordlist_unavailable"
    POLICY_UNAVAILABLE = "policy_unavailable"
    PLAN_LIMIT = "plan_limit"
    STAGE_BUDGET = "stage_budget"
    OUTPUT_LIMIT = "output_limit"
    ISSUE_LIMIT = "issue_limit"
    VALIDATION_LIMIT = "validation_limit"
    BASELINE_UNAVAILABLE = "baseline_unavailable"
    MALFORMED_REPORT = "malformed_report"
    WRONG_TARGET = "wrong_target"
    SPAWN_ERROR = "spawn_error"
    EXECUTION_ERROR = "execution_error"
    UNIT_TIMEOUT = "unit_timeout"


TargetedSeverity = Literal["low", "medium", "high", "critical"]
TargetedObservationKind = Literal[
    "administration",
    "api_surface",
    "service_identity",
    "device_identity",
]


@dataclass(frozen=True, slots=True)
class TargetedUnit:
    """One tool invocation selected for one open TCP endpoint."""

    ip: str
    port: int
    protocol: str
    service: str
    tool: TargetedTool
    transport: str | None = None

    @property
    def identity(self) -> tuple[str, int, str, TargetedTool]:
        return (self.ip, self.port, self.protocol, self.tool)


@dataclass(frozen=True, slots=True)
class TargetedIssue:
    """Affirmative security evidence emitted by a targeted adapter."""

    issue_key: str
    title: str
    description: str
    severity: TargetedSeverity
    recommendation: str
    evidence: str
    cve_id: str | None = None
    cvss_score: float | None = None
    references: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TargetedObservation:
    """Bounded non-vulnerability evidence emitted by a targeted adapter."""

    observation_key: str
    kind: TargetedObservationKind
    summary: str
    evidence: str
    path: str | None = None
    rule_id: str | None = None
    policy_version: str | None = None


@dataclass(slots=True)
class TargetedUnitResult:
    """Result retained for one completed or incomplete targeted unit."""

    unit: TargetedUnit
    outcome: TargetedOutcome
    issues: list[TargetedIssue] = field(default_factory=list)
    observations: list[TargetedObservation] = field(default_factory=list)
    exit_code: int | None = None
    reason_code: TargetedGapReason | None = None
    diagnostic: str | None = None


def _empty_outcome_counts() -> dict[TargetedOutcome, int]:
    return {outcome: 0 for outcome in TargetedOutcome}


def _empty_tool_counts() -> dict[TargetedTool, dict[TargetedOutcome, int]]:
    return {tool: _empty_outcome_counts() for tool in TargetedTool}


def _empty_tool_scalar_counts() -> dict[TargetedTool, int]:
    return {tool: 0 for tool in TargetedTool}


def _empty_tool_gap_counts() -> dict[TargetedTool, dict[TargetedGapReason, int]]:
    return {tool: {reason: 0 for reason in TargetedGapReason} for tool in TargetedTool}


@dataclass(slots=True)
class TargetedStageSummary:
    """Bounded aggregate counters for one targeted stage."""

    eligible: int = 0
    planned: int = 0
    omitted: int = 0
    omitted_unlisted: int = 0
    completed: int = 0
    failed: int = 0
    timed_out: int = 0
    skipped: int = 0
    finding_candidates: int = 0
    observation_candidates: int = 0
    per_tool: dict[TargetedTool, dict[TargetedOutcome, int]] = field(
        default_factory=_empty_tool_counts
    )
    plan_limit_by_tool: dict[TargetedTool, int] = field(
        default_factory=_empty_tool_scalar_counts
    )
    gap_by_tool: dict[TargetedTool, dict[TargetedGapReason, int]] = field(
        default_factory=_empty_tool_gap_counts
    )
