from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AIText = Annotated[str, Field(min_length=3, max_length=4000)]
AIShortText = Annotated[str, Field(min_length=3, max_length=2000)]


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


class ScanAIAnalysisUnavailable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    status: Literal["unavailable"]


class ScanAIAnalysisNotRequested(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    status: Literal["not_requested"]


class _ScanAIAnalysisJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    analysis_id: UUID
    provider: str
    model: str
    context_version: str
    prompt_version: str
    created_at: datetime
    updated_at: datetime


class ScanAIAnalysisQueued(_ScanAIAnalysisJob):
    status: Literal["pending", "processing"]


class ScanAIAnalysisFailed(_ScanAIAnalysisJob):
    status: Literal["failed"]
    completed_at: datetime


class ScanAIAnalysisCompleted(_ScanAIAnalysisJob):
    status: Literal["completed"]
    completed_at: datetime
    analysis: ScanAIAnalysis


ScanAIAnalysisResponse = Annotated[
    ScanAIAnalysisUnavailable
    | ScanAIAnalysisNotRequested
    | ScanAIAnalysisQueued
    | ScanAIAnalysisFailed
    | ScanAIAnalysisCompleted,
    Field(discriminator="status"),
]
