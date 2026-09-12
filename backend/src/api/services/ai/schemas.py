from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.core.severity import Severity
from api.schemas.read import ScanMode, SeverityBreakdown

AIText = Annotated[str, Field(min_length=3, max_length=4000)]
AIShortText = Annotated[str, Field(min_length=3, max_length=2000)]
AI_CONTEXT_VERSION = "1"


class AIFindingContext(BaseModel):
    """Bounded, deterministic evidence for one finding sent to a provider."""

    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    host_id: UUID | None
    host_ip: IPv4Address | None
    port: Annotated[int | None, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"] | None
    service: str | None
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
    title: Annotated[str, Field(min_length=3, max_length=500)]
    description: Annotated[str, Field(min_length=3, max_length=4000)]
    recommendation: Annotated[str, Field(min_length=3, max_length=2000)]
    evidence: Annotated[str, Field(min_length=3, max_length=4000)]
    references: Annotated[list[str], Field(max_length=10)]


class ScanAIContext(BaseModel):
    """Versioned and bounded source of truth for one scan analysis."""

    model_config = ConfigDict(extra="forbid")

    context_version: Literal["1"] = AI_CONTEXT_VERSION
    scan_id: UUID
    timestamp: datetime
    subnet: str
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


class AIRecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["immediate", "high", "medium", "low"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: AIShortText
    related_finding_ids: Annotated[list[UUID], Field(max_length=15)]


class AIFindingExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    why_it_matters: AIShortText
    plain_language_explanation: AIShortText
    recommendation: AIShortText
    evidence_used: Annotated[list[AIShortText], Field(max_length=10)]
    uncertainty: Annotated[str | None, Field(max_length=1000)]


class ScanAIAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: AIText
    overall_assessment: AIText
    plain_language_summary: AIText
    priority_actions: Annotated[list[AIRecommendedAction], Field(max_length=15)]
    important_findings: Annotated[list[AIFindingExplanation], Field(max_length=15)]
    uncertainties: Annotated[list[AIShortText], Field(max_length=20)]
