from __future__ import annotations

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from sqlmodel import Session, func, select

from api.core.scan_read import scan_duration_seconds
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
    ProviderScanAIAnalysis,
    ScanAIAnalysis,
)
from api.schemas.read import ScanMode, SeverityBreakdown
from api.services.read import get_scan_risk_summary

AI_CONTEXT_VERSION = "2"

MAX_AI_FINDINGS = 15
_REFERENCE_PATTERN = re.compile(r"\b(?:finding|machine)_[1-9][0-9]*\b")


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
    risk_score: Annotated[float | None, Field(ge=0, le=100)]
    exploitability: Annotated[float | None, Field(ge=0, le=1)]
    epss_score: Annotated[float | None, Field(ge=0, le=1)]
    epss_percentile: Annotated[float | None, Field(ge=0, le=1)]
    is_kev: bool
    known_ransomware: bool


class ScanAIContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_version: Literal["2"] = AI_CONTEXT_VERSION
    scan_mode: ScanMode
    duration_seconds: Annotated[int | None, Field(ge=0)]
    host_count: Annotated[int, Field(ge=0)]
    total_findings: Annotated[int, Field(ge=0)]
    scored_findings: Annotated[int, Field(ge=0)]
    confirmed_findings: Annotated[int, Field(ge=0)]
    kev_findings: Annotated[int, Field(ge=0)]
    average_risk_score: Annotated[float | None, Field(ge=0, le=100)]
    max_risk_score: Annotated[float | None, Field(ge=0, le=100)]
    severity: SeverityBreakdown
    top_findings: Annotated[list[AIFindingContext], Field(max_length=15)]

    _finding_ids_by_ref: dict[str, UUID] = PrivateAttr(default_factory=dict)
    _display_values_by_ref: dict[str, str] = PrivateAttr(default_factory=dict)


class ScanAINotReadyError(ValueError):
    pass


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

    cve_ids = {
        finding.cve_id.upper()
        for finding in risk.top_findings
        if finding.cve_id is not None
    }
    epss_by_cve = _epss_by_cve(session, cve_ids)
    kev_by_cve = _kev_by_cve(session, cve_ids)

    findings = []
    finding_ids_by_ref: dict[str, UUID] = {}
    display_values_by_ref: dict[str, str] = {}
    machine_refs: dict[UUID | None, str] = {}
    for index, finding in enumerate(risk.top_findings, start=1):
        cve_id = finding.cve_id.upper() if finding.cve_id is not None else None
        epss = epss_by_cve.get(cve_id) if cve_id is not None else None
        kev = kev_by_cve.get(cve_id) if cve_id is not None else None
        finding_ref = f"finding_{index}"
        machine_ref = _machine_ref(machine_refs, finding.host_id)
        finding_ids_by_ref[finding_ref] = finding.finding_id
        display_values_by_ref[finding_ref] = finding.title
        if machine_ref is not None:
            display_values_by_ref[machine_ref] = (
                finding.host_hostname
                or str(finding.host_ip)
                or "the affected machine"
            )
        findings.append(
            AIFindingContext(
                finding_ref=finding_ref,
                machine_ref=machine_ref,
                cve_id=finding.cve_id,
                cvss_score=finding.cvss_score,
                severity=finding.severity,
                confidence=finding.confidence,
                risk_score=finding.risk_score,
                exploitability=finding.exploitability,
                epss_score=epss.epss_score if epss is not None else None,
                epss_percentile=epss.percentile if epss is not None else None,
                is_kev=kev is not None,
                known_ransomware=kev.known_ransomware if kev is not None else False,
            )
        )

    context = ScanAIContext(
        scan_mode=scan.scan_mode,
        duration_seconds=scan_duration_seconds(scan.status, scan.metadata_json),
        host_count=host_count,
        total_findings=risk.total_findings,
        scored_findings=risk.scored_findings,
        confirmed_findings=risk.confirmed_findings,
        kev_findings=risk.kev_findings,
        average_risk_score=risk.average_risk_score,
        max_risk_score=risk.max_risk_score,
        severity=risk.severity,
        top_findings=findings,
    )
    context._finding_ids_by_ref = finding_ids_by_ref
    context._display_values_by_ref = display_values_by_ref
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
                why_it_matters=_replace_references(
                    item.why_it_matters, context._display_values_by_ref
                ),
                plain_language_explanation=_replace_references(
                    item.plain_language_explanation,
                    context._display_values_by_ref,
                ),
                recommendation=_replace_references(
                    item.recommendation, context._display_values_by_ref
                ),
                evidence_used=[
                    _replace_references(value, context._display_values_by_ref)
                    for value in item.evidence_used
                ],
                uncertainty=(
                    _replace_references(
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
                title=_replace_references(item.title, context._display_values_by_ref),
                description=_replace_references(
                    item.description, context._display_values_by_ref
                ),
                related_finding_ids=[
                    context._finding_ids_by_ref[reference]
                    for reference in item.related_finding_refs
                ],
            )
        )
    return ScanAIAnalysis(
        executive_summary=_replace_references(
            analysis.executive_summary, context._display_values_by_ref
        ),
        overall_assessment=_replace_references(
            analysis.overall_assessment, context._display_values_by_ref
        ),
        plain_language_summary=_replace_references(
            analysis.plain_language_summary, context._display_values_by_ref
        ),
        priority_actions=actions,
        important_findings=explanations,
        uncertainties=[
            _replace_references(value, context._display_values_by_ref)
            for value in analysis.uncertainties
        ],
    )


def _machine_ref(
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


def replace_ai_references(value: str, display_values_by_ref: dict[str, str]) -> str:
    return _REFERENCE_PATTERN.sub(
        lambda match: display_values_by_ref[match.group(0)], value
    )


def assign_machine_ref(
    machine_refs: dict[UUID | None, str], host_id: UUID | None
) -> str | None:
    return _machine_ref(machine_refs, host_id)


def _replace_references(value: str, display_values_by_ref: dict[str, str]) -> str:
    return replace_ai_references(value, display_values_by_ref)


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
