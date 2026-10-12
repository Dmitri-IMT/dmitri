from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import TypedDict

from api.schemas.ai import AILanguage, ScanAIAnalysisCompleted
from api.schemas.read import ScanDetailResponse, ScanRiskSummaryResponse

ReportKind = Literal["explained", "technical"]


class ReportService(TypedDict):
    port: int
    protocol: str
    service: str
    version: str | None
    family: str
    purpose: str
    finding_count: int


class ReportDevice(TypedDict):
    address: str
    hostname: str
    display_name: str
    manufacturer: str | None
    model: str | None
    identity_confidence: str
    identity_evidence: list[str]
    identity_conflicts: list[str]
    machine_type: str
    os: str | None
    finding_count: int
    correlation_count: int
    observation_count: int
    severity_counts: dict[str, int]
    severity: str | None
    open_ports: int
    groups: list[str]
    review_exposures: int
    checks_completed: int
    checks_incomplete: int
    status: Literal["review", "no_alerts"]
    services: list[ReportService]
    note: str
    unreadable_fields: list[str]


class ReportObservation(TypedDict):
    title: str
    description: str
    evidence: str
    recommendation: str


class ReportAdvisoryNote(TypedDict):
    cve_id: str
    explanation: str
    url: str


class ReportIssueGroup(TypedDict):
    id: str
    address: str | None
    hostname: str | None
    category: str
    family: str
    basis: str
    title: str
    port: int | None
    protocol: str | None
    service: str | None
    version: str | None
    finding_count: int
    severity: str | None
    severity_counts: dict[str, int]
    cves: list[str]
    purpose: str
    meaning: str
    impact: str
    conditions: str
    uncertainty: str
    steps: list[str]
    verify: str
    recorded_observations: list[ReportObservation]
    advisory_notes: list[ReportAdvisoryNote]


class ReportFinding(TypedDict):
    finding_id: str
    group: str
    address: str | None
    port: int | None
    protocol: str | None
    title: str
    severity: str
    basis: str
    advisory_effects: list[str]
    advisory_description: str | None
    advisory_fetched_at: str | None
    reference: str | None
    description: str
    recommendation: str
    evidence: str
    plain_language_explanation: str | None
    why_it_matters: str | None
    uncertainty: str | None


class ReportSource(TypedDict):
    title: str
    url: str


class ReportAction(TypedDict):
    priority: Literal["immediate", "high", "medium", "low"]
    title: str
    description: str
    related_finding_ids: list[str]


class ReportEducation(TypedDict):
    version: str
    devices: list[ReportDevice]
    issue_groups: list[ReportIssueGroup]
    severity_counts: dict[str, int]
    evidence_counts: dict[str, int]
    service_counts: dict[str, int]
    affected_hosts: int
    hosts_without_findings: int
    unassigned_findings: int
    evidence_completeness: str
    checks_completed: int
    checks_incomplete: int
    coverage_recorded: bool
    enrichment: dict[str, int]
    appendix: list[ReportFinding]
    sources: list[ReportSource]


class ExplainedReportSections(ReportEducation):
    __pydantic_config__ = ConfigDict(extra="forbid")

    scan_timestamp: datetime
    scope: str
    scan_mode: str
    overview: str
    ai_explanation_available: bool
    actions: list[ReportAction]
    method: str
    limitations: list[str]


class TechnicalReportSections(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")

    scan_timestamp: datetime
    scope: str
    scan_mode: str
    scan: ScanDetailResponse
    risk_summary: ScanRiskSummaryResponse
    ai_analysis: ScanAIAnalysisCompleted | None


class ScanReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    kind: ReportKind
    language: AILanguage
    generated_at: datetime
    filename: str
    content_type: Literal["application/pdf", "application/json"]
    sections: ExplainedReportSections | TechnicalReportSections

    @model_validator(mode="after")
    def match_report_kind(self) -> ScanReportResponse:
        explained = "devices" in self.sections
        if explained != (self.kind == "explained"):
            raise ValueError("report sections do not match kind")
        expected = "application/pdf" if explained else "application/json"
        if self.content_type != expected:
            raise ValueError("report content type does not match kind")
        return self
