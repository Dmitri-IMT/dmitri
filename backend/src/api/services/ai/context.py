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
    CPERecord,
    EpssRecord,
    FindingRecord,
    KevRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas.ai import (
    AIFindingNote,
    AIFixTask,
    AISourceLink,
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
from api.services.products import normalize_product_text, observed_product
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
    service: str | None = None
    product: str | None = None
    version: str | None = None
    version_affected: Literal["yes", "no", "unknown"] | None = None
    fix_options: list[AIFixOptionContext] = Field(default_factory=list)

    _fix_sources: list[AISourceLink] = PrivateAttr(default_factory=list)


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
                epss_score=(
                    epss.epss_score if epss is not None else finding.epss_score
                ),
                epss_percentile=epss.percentile if epss is not None else None,
                is_kev=kev is not None or finding.kev_listed,
                known_ransomware=(
                    kev.known_ransomware if kev is not None
                    else finding.known_ransomware
                ),
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
    describe_observed_products(session, bundle.contexts, bundle.finding_ids_by_ref)
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


def describe_observed_products(
    session: Session,
    findings: Sequence[AIFindingContext],
    finding_ids_by_ref: dict[str, UUID],
) -> None:
    finding_ids = [finding_ids_by_ref[finding.finding_ref] for finding in findings]
    if not finding_ids:
        return
    services = dict(
        session.exec(
            select(FindingRecord.finding_id, ServiceRecord.name)
            .join(ServiceRecord, ServiceRecord.port_id == FindingRecord.port_id)
            .where(FindingRecord.finding_id.in_(finding_ids))
        ).all()
    )
    cpes: dict[UUID, list[str]] = {}
    for finding_id, cpe in session.exec(
        select(FindingRecord.finding_id, CPERecord.cpe)
        .join(CPERecord, CPERecord.port_id == FindingRecord.port_id)
        .where(FindingRecord.finding_id.in_(finding_ids))
    ).all():
        cpes.setdefault(finding_id, []).append(cpe)
    for finding in findings:
        finding_id = finding_ids_by_ref[finding.finding_ref]
        finding.service = normalize_product_text(services.get(finding_id))
        observed = observed_product(cpes.get(finding_id, []))
        if observed is not None:
            finding.product, finding.version = observed


TASK_TIME_ORDER = ("5_minutes", "30_minutes", "1_hour", "half_day", "1_day", "longer")
_PRIORITY_ORDER = {"immediate": 0, "high": 1, "medium": 2, "low": 3}
MAX_TASK_SOURCES = 3


def materialize_scan_ai_analysis(
    context: ScanAIContext,
    analysis: ProviderScanAIAnalysis,
) -> ScanAIAnalysis:
    known_finding_refs = set(context._finding_ids_by_ref)
    known_refs = known_finding_refs | set(context._display_values_by_ref)
    if not _uses_only_known_references(analysis, known_finding_refs, known_refs):
        raise ValueError("analysis contains an unknown reference")

    display = context._display_values_by_ref
    findings_by_ref = {finding.finding_ref: finding for finding in context.top_findings}

    def highest_risk(references: list[str]) -> float | None:
        scores = [
            findings_by_ref[reference].risk_score
            for reference in references
            if findings_by_ref[reference].risk_score is not None
        ]
        return max(scores, default=None)

    ordered = sorted(
        analysis.tasks,
        key=lambda task: (
            TASK_TIME_ORDER.index(task.time),
            -(highest_risk(task.fixes) or -1),
            -len(task.fixes),
        ),
    )
    tasks = []
    rank_by_ref: dict[str, int] = {}
    for rank, task in enumerate(ordered, start=1):
        for reference in task.fixes:
            rank_by_ref.setdefault(reference, rank)
        tasks.append(
            AIFixTask(
                rank=rank,
                priority=priority_for_references(context, task.fixes),
                title=replace_ai_references(task.title, display),
                who=task.who,
                time=task.time,
                steps=[replace_ai_references(step, display) for step in task.steps],
                fallback=(
                    replace_ai_references(task.fallback, display)
                    if task.fallback is not None
                    else None
                ),
                fixes_fully=task.fixes_fully,
                finding_ids=[
                    context._finding_ids_by_ref[reference] for reference in task.fixes
                ],
                highest_risk_score=highest_risk(task.fixes),
                sources=_task_sources(findings_by_ref, task.fixes),
            )
        )
    return ScanAIAnalysis(
        summary=replace_ai_references(analysis.summary, display),
        tasks=tasks,
        findings=[
            AIFindingNote(
                finding_id=context._finding_ids_by_ref[note.finding_ref],
                plain_title=replace_ai_references(note.plain_title, display),
                cause=replace_ai_references(note.cause, display),
                what_could_happen=replace_ai_references(
                    note.what_could_happen, display
                ),
                task_rank=rank_by_ref.get(note.finding_ref),
            )
            for note in analysis.findings
        ],
        not_checked=(
            replace_ai_references(analysis.not_checked, display)
            if analysis.not_checked is not None
            else None
        ),
    )


def priority_for_references(context: ScanAIContext, references: list[str]) -> str:
    findings_by_reference = {
        finding.finding_ref: finding for finding in context.top_findings
    }
    priorities = [
        _priority_for_finding(findings_by_reference[reference])
        for reference in references
        if reference in findings_by_reference
    ]
    return min(priorities, key=_PRIORITY_ORDER.__getitem__, default="low")


def _priority_for_finding(finding: AIFindingContext) -> str:
    if finding.is_kev:
        return "immediate"
    if (
        (finding.risk_score is not None and finding.risk_score >= 70)
        or (finding.cvss_score is not None and finding.cvss_score >= 9)
        or (finding.epss_score is not None and finding.epss_score >= 0.7)
    ):
        return "high"
    if (finding.risk_score is not None and finding.risk_score >= 40) or (
        finding.cvss_score is not None and finding.cvss_score >= 7
    ):
        return "medium"
    return "low"


def _task_sources(
    findings_by_ref: dict[str, AIFindingContext], references: list[str]
) -> list[AISourceLink]:
    sources: dict[str, AISourceLink] = {}
    for reference in references:
        candidates = findings_by_ref[reference]._fix_sources
        if candidates and candidates[0].url not in sources:
            sources[candidates[0].url] = candidates[0]
    return list(sources.values())[:MAX_TASK_SOURCES]


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
    if any(note.finding_ref not in known_finding_refs for note in analysis.findings):
        return False
    if any(
        reference not in known_finding_refs
        for task in analysis.tasks
        for reference in task.fixes
    ):
        return False
    return all(
        reference in known_refs
        for value in _text_values(analysis)
        for reference in _REFERENCE_PATTERN.findall(value)
    )


def _text_values(analysis: ProviderScanAIAnalysis) -> list[str]:
    values = [analysis.summary]
    if analysis.not_checked is not None:
        values.append(analysis.not_checked)
    for task in analysis.tasks:
        values.extend([task.title, *task.steps])
        if task.fallback is not None:
            values.append(task.fallback)
    for note in analysis.findings:
        values.extend([note.plain_title, note.cause, note.what_could_happen])
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
