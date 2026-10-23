from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from sqlmodel import Session, func, select

from api.core.scan_read import scan_duration_seconds, scan_terminated_by
from api.core.severity import Severity
from api.models.persistence import (
    EpssRecord,
    KevRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.schemas.ai import (
    AIFindingExplanation,
    AIRecommendedAction,
    FixActor,
    FixEffort,
    ProviderScanAIAnalysis,
    ScanAIAnalysis,
)
from api.schemas.read import (
    FindingEvidenceSummary,
    FindingRead,
    MachineType,
    ScanMode,
    ScanStatus,
    SeverityBreakdown,
)
from api.schemas.scan import TERMINATED_BY_USER_CANCEL
from api.services.read import get_scan_detail, get_scan_risk_summary
from api.services.scan_evidence import (
    EvidenceCompleteness,
    evidence_completeness,
    incomplete_check_count,
    is_cve_correlation,
    parse_coverage,
)

AI_CONTEXT_VERSION = "6"

MAX_AI_FINDINGS = 15
_REFERENCE_PATTERN = re.compile(r"\b(?:finding|machine)_[1-9][0-9]*\b")


class AIFixOptionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effort: FixEffort
    who: FixActor
    steps: list[str]
    fixed_version: str | None
    fixes_fully: bool
    source_name: str


class FixResearchTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cve_id: str
    product: str | None
    version: str | None
    service: str | None
    severity: Severity
    cvss_score: float | None
    is_kev: bool
    kev_required_action: str | None
    epss_score: float | None


class AIFindingContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_ref: Annotated[str, Field(pattern=r"^finding_[1-9][0-9]*$")]
    machine_ref: Annotated[
        str | None, Field(default=None, pattern=r"^machine_[1-9][0-9]*$")
    ]
    cve_id: str | None
    cvss_score: Annotated[float | None, Field(ge=0, le=10)]
    severity: Severity
    confidence: Literal["tentative", "probable", "confirmed"] | None
    evidence_basis: Literal[
        "cve_correlation", "target_observation", "unknown"
    ] = "unknown"
    detection_method: Literal[
        "version_correlation",
        "configuration_observation",
        "specific_check",
        "textual_reference",
        "unknown",
    ] = "unknown"
    evidence_status: Literal[
        "supported", "inconclusive", "conflicting", "unknown"
    ] = "unknown"
    evidence_truncated: bool = False
    risk_score: Annotated[float | None, Field(ge=0, le=100)]
    exploitability: Annotated[float | None, Field(ge=0, le=1)]
    epss_score: Annotated[float | None, Field(ge=0, le=1)]
    epss_percentile: Annotated[float | None, Field(ge=0, le=1)]
    is_kev: bool
    known_ransomware: bool
    version_affected: Literal["yes", "no", "unknown"] | None = None
    fix_options: list[AIFixOptionContext] = Field(default_factory=list)


class ScanAIContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_version: Literal["6"] = AI_CONTEXT_VERSION
    scan_mode: ScanMode
    evidence_completeness: EvidenceCompleteness = "unknown"
    incomplete_check_count: Annotated[int, Field(ge=0)] = 0
    duration_seconds: Annotated[int | None, Field(ge=0)]
    stopped_by: Literal["operator", "timeout", "error"] | None = None
    host_count: Annotated[int, Field(ge=0)]
    total_findings: Annotated[int, Field(ge=0)]
    scored_findings: Annotated[int, Field(ge=0)]
    confirmed_findings: Annotated[int, Field(ge=0)]
    kev_findings: Annotated[int, Field(ge=0)]
    average_risk_score: Annotated[float | None, Field(ge=0, le=100)]
    max_risk_score: Annotated[float | None, Field(ge=0, le=100)]
    severity: SeverityBreakdown
    top_findings: Annotated[list[AIFindingContext], Field(max_length=15)]
    evidence_summary: FindingEvidenceSummary

    _finding_ids_by_ref: dict[str, UUID] = PrivateAttr(default_factory=dict)
    _display_values_by_ref: dict[str, str] = PrivateAttr(default_factory=dict)


class ChatAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_findings: Annotated[int, Field(ge=0)]
    scored_findings: Annotated[int, Field(ge=0)]
    confirmed_findings: Annotated[int, Field(ge=0)]
    kev_findings: Annotated[int, Field(ge=0)]
    average_risk_score: Annotated[float | None, Field(ge=0, le=100)]
    max_risk_score: Annotated[float | None, Field(ge=0, le=100)]
    severity: SeverityBreakdown


class MachineVulnerabilityCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_ref: Annotated[str, Field(pattern=r"^machine_[1-9][0-9]*$")]
    finding_count: Annotated[int, Field(ge=0)]
    severity: SeverityBreakdown
    max_risk_score: Annotated[float | None, Field(ge=0, le=100)] = None


class ScanChatContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_version: Literal["6"] = AI_CONTEXT_VERSION
    scope: Literal["scan"] = "scan"
    scan_mode: ScanMode
    status: ScanStatus
    evidence_completeness: EvidenceCompleteness = "unknown"
    incomplete_check_count: Annotated[int, Field(ge=0)] = 0
    host_count: Annotated[int, Field(ge=0)]
    aggregate: ChatAggregate
    top_findings: list[AIFindingContext]
    machine_vulnerability_summary: list[MachineVulnerabilityCount]
    evidence_summary: FindingEvidenceSummary


class FindingChatContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_version: Literal["6"] = AI_CONTEXT_VERSION
    scope: Literal["finding"] = "finding"
    finding: AIFindingContext
    evidence_summary: FindingEvidenceSummary


class HostChatContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_version: Literal["6"] = AI_CONTEXT_VERSION
    scope: Literal["host"] = "host"
    machine_ref: Annotated[str, Field(pattern=r"^machine_[1-9][0-9]*$")]
    machine_type: MachineType
    vulnerability_count: Annotated[int, Field(ge=0)]
    highest_severity: Severity | None
    open_ports_count: Annotated[int, Field(ge=0)]
    findings: list[AIFindingContext]
    evidence_summary: FindingEvidenceSummary


AIChatContext = ScanChatContext | FindingChatContext | HostChatContext


class ScanAINotReadyError(ValueError):
    pass


@dataclass
class FindingContextBundle:
    """Placeholder-only finding rows plus the local maps that resolve them."""

    contexts: list[AIFindingContext] = field(default_factory=list)
    finding_ids_by_ref: dict[str, UUID] = field(default_factory=dict)
    display_values_by_ref: dict[str, str] = field(default_factory=dict)


def build_finding_contexts(
    findings: Sequence[FindingRead],
    *,
    machine_refs: dict[UUID | None, str],
    epss_by_cve: dict[str, EpssRecord] | None = None,
    kev_by_cve: dict[str, KevRecord] | None = None,
) -> FindingContextBundle:
    """Turn findings into `finding_N` context rows and their display maps."""
    bundle = FindingContextBundle()
    for index, finding in enumerate(findings, start=1):
        cve_id = finding.cve_id.upper() if finding.cve_id is not None else None
        epss = (epss_by_cve or {}).get(cve_id) if cve_id is not None else None
        kev = (kev_by_cve or {}).get(cve_id) if cve_id is not None else None
        finding_ref = f"finding_{index}"
        machine_ref = assign_machine_ref(machine_refs, finding.host_id)
        bundle.finding_ids_by_ref[finding_ref] = finding.finding_id
        bundle.display_values_by_ref[finding_ref] = finding.title
        if machine_ref is not None:
            bundle.display_values_by_ref[machine_ref] = machine_display_value(
                finding.host_hostname, finding.host_ip
            )
        bundle.contexts.append(
            AIFindingContext(
                finding_ref=finding_ref,
                machine_ref=machine_ref,
                cve_id=finding.cve_id,
                cvss_score=finding.cvss_score,
                severity=finding.severity,
                confidence=finding.confidence,
                evidence_basis=(
                    "cve_correlation"
                    if is_cve_correlation(finding.cve_id, finding.source)
                    else (
                        "target_observation"
                        if finding.evidence_observations
                        else "unknown"
                    )
                ),
                detection_method=finding.detection_method,
                evidence_status=finding.evidence_status,
                evidence_truncated=finding.evidence_truncated,
                risk_score=finding.risk_score,
                exploitability=finding.exploitability,
                epss_score=epss.epss_score if epss is not None else None,
                epss_percentile=epss.percentile if epss is not None else None,
                is_kev=kev is not None,
                known_ransomware=kev.known_ransomware if kev is not None else False,
            )
        )
    return bundle


def machine_display_value(hostname: str | None, ip: object | None) -> str:
    return hostname or str(ip or "") or "the affected machine"


def build_scan_ai_context(
    session: Session,
    scan: ScanRecord,
    *,
    max_findings: int = 10,
) -> ScanAIContext | None:
    if not 1 <= max_findings <= MAX_AI_FINDINGS:
        raise ValueError(
            f"max_findings must be between 1 and {MAX_AI_FINDINGS}"
        )
    if scan.status != "completed":
        raise ScanAINotReadyError("scan must be completed before AI analysis")

    risk = get_scan_risk_summary(
        session,
        scan.scan_id,
        org_id=scan.org_id,
        top_limit=max_findings,
    )
    if risk is None:
        return None

    host_count = session.exec(
        select(func.count())
        .select_from(ScanHostRecord)
        .where(ScanHostRecord.scan_id == scan.scan_id)
    ).one()
    detail = get_scan_detail(session, scan.scan_id, org_id=scan.org_id)
    if detail is None or detail.evidence_summary is None:
        return None

    cve_ids = {
        finding.cve_id.upper()
        for finding in risk.top_findings
        if finding.cve_id is not None
    }
    epss_by_cve = _epss_by_cve(session, cve_ids)
    kev_by_cve = _kev_by_cve(session, cve_ids)

    machine_refs: dict[UUID | None, str] = {}
    bundle = build_finding_contexts(
        risk.top_findings,
        machine_refs=machine_refs,
        epss_by_cve=epss_by_cve,
        kev_by_cve=kev_by_cve,
    )
    coverage = parse_coverage(scan.coverage_json)

    context = ScanAIContext(
        scan_mode=scan.scan_mode,
        evidence_completeness=evidence_completeness(scan.metadata_json, coverage),
        incomplete_check_count=incomplete_check_count(coverage),
        duration_seconds=scan_duration_seconds(scan.status, scan.metadata_json),
        stopped_by={
            TERMINATED_BY_USER_CANCEL: "operator",
            "timeout": "timeout",
            "error": "error",
        }.get(scan_terminated_by(scan.metadata_json)),
        host_count=host_count,
        total_findings=risk.total_findings,
        scored_findings=risk.scored_findings,
        confirmed_findings=risk.confirmed_findings,
        kev_findings=risk.kev_findings,
        average_risk_score=risk.average_risk_score,
        max_risk_score=risk.max_risk_score,
        severity=risk.severity,
        top_findings=bundle.contexts,
        evidence_summary=detail.evidence_summary,
    )
    context._finding_ids_by_ref = bundle.finding_ids_by_ref
    context._display_values_by_ref = bundle.display_values_by_ref
    return context


def materialize_scan_ai_analysis(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
) -> ScanAIAnalysis:
    known_finding_refs = set(context._finding_ids_by_ref)
    known_refs = known_finding_refs | set(context._display_values_by_ref)
    if not _uses_only_known_references(
        analysis, known_finding_refs, known_refs
    ):
        raise ValueError("analysis contains an unknown reference")

    explanations = []
    for item in analysis.important_findings:
        explanations.append(
            AIFindingExplanation(
                finding_id=context._finding_ids_by_ref[item.finding_ref],
                why_it_matters=replace_ai_references(
                    item.why_it_matters, context._display_values_by_ref
                ),
                plain_language_explanation=replace_ai_references(
                    item.plain_language_explanation,
                    context._display_values_by_ref,
                ),
                recommendation=replace_ai_references(
                    item.recommendation, context._display_values_by_ref
                ),
                evidence_used=[
                    replace_ai_references(value, context._display_values_by_ref)
                    for value in item.evidence_used
                ],
                uncertainty=(
                    replace_ai_references(
                        item.uncertainty, context._display_values_by_ref
                    )
                    if item.uncertainty is not None
                    else None
                ),
            )
        )
    actions = []
    for item in analysis.priority_actions:
        actions.append(
            AIRecommendedAction(
                priority=item.priority,
                title=replace_ai_references(item.title, context._display_values_by_ref),
                description=replace_ai_references(
                    item.description, context._display_values_by_ref
                ),
                related_finding_ids=[
                    context._finding_ids_by_ref[reference]
                    for reference in item.related_finding_refs
                ],
            )
        )
    return ScanAIAnalysis(
        executive_summary=replace_ai_references(
            analysis.executive_summary, context._display_values_by_ref
        ),
        overall_assessment=replace_ai_references(
            analysis.overall_assessment, context._display_values_by_ref
        ),
        plain_language_summary=replace_ai_references(
            analysis.plain_language_summary, context._display_values_by_ref
        ),
        priority_actions=actions,
        important_findings=explanations,
        uncertainties=[
            replace_ai_references(value, context._display_values_by_ref)
            for value in analysis.uncertainties
        ],
    )


def assign_machine_ref(
    machine_refs: dict[UUID | None, str], host_id: UUID | None
) -> str | None:
    if host_id is None:
        return None
    if host_id not in machine_refs:
        machine_refs[host_id] = f"machine_{len(machine_refs) + 1}"
    return machine_refs[host_id]


def _uses_only_known_references(
    analysis: ProviderScanAIAnalysis,
    known_finding_refs: set[str],
    known_refs: set[str],
) -> bool:
    if any(
        item.finding_ref not in known_finding_refs
        for item in analysis.important_findings
    ):
        return False
    if any(
        reference not in known_finding_refs
        for action in analysis.priority_actions
        for reference in action.related_finding_refs
    ):
        return False
    return all(
        reference in known_refs
        for value in _text_values(analysis)
        for reference in _REFERENCE_PATTERN.findall(value)
    )


def _text_values(analysis: ProviderScanAIAnalysis) -> list[str]:
    values = [
        analysis.executive_summary,
        analysis.overall_assessment,
        analysis.plain_language_summary,
        *analysis.uncertainties,
    ]
    for action in analysis.priority_actions:
        values.extend([action.title, action.description])
    for explanation in analysis.important_findings:
        values.extend(
            [
                explanation.why_it_matters,
                explanation.plain_language_explanation,
                explanation.recommendation,
                *explanation.evidence_used,
            ]
        )
        if explanation.uncertainty is not None:
            values.append(explanation.uncertainty)
    return values


def reference_names(value: str) -> list[str]:
    """Return every `finding_N` / `machine_N` placeholder in the text."""
    return _REFERENCE_PATTERN.findall(value)


def replace_ai_references(value: str, display_values_by_ref: dict[str, str]) -> str:
    return _REFERENCE_PATTERN.sub(
        lambda match: display_values_by_ref[match.group(0)], value
    )


def _epss_by_cve(session: Session, cve_ids: set[str]) -> dict[str, EpssRecord]:
    if not cve_ids:
        return {}
    rows = session.exec(
        select(EpssRecord).where(EpssRecord.cve_id.in_(cve_ids))
    ).all()
    return {row.cve_id.upper(): row for row in rows}


def _kev_by_cve(session: Session, cve_ids: set[str]) -> dict[str, KevRecord]:
    if not cve_ids:
        return {}
    rows = session.exec(
        select(KevRecord).where(KevRecord.cve_id.in_(cve_ids))
    ).all()
    return {row.cve_id.upper(): row for row in rows}
