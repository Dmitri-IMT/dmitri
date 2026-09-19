from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AIText = Annotated[str, Field(min_length=3, max_length=4000)]
AIShortText = Annotated[str, Field(min_length=3, max_length=2000)]
FindingReference = Annotated[str, Field(pattern=r"^finding_[1-9][0-9]*$")]
AILanguage = Literal["en", "pt-BR", "ru"]


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=3, max_length=1000)]
    language: AILanguage = "en"


class AIContextChatRequest(AIChatRequest):
    """Question addressed to a reusable UI context (scan, host or finding)."""

    scope: Literal["scan", "host", "finding"]
    context_id: UUID


class AIChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: AIText
    uncertainties: Annotated[list[AIShortText], Field(max_length=10)]
    referenced_finding_ids: Annotated[list[UUID], Field(max_length=15)]


class AIChatHistoryEntry(AIChatResponse):
    message_id: UUID
    question: AIShortText
    created_at: datetime


class AIChatHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[AIChatHistoryEntry]


class AIUsageEntry(BaseModel):
    """Non-sensitive provider usage metadata for an organization dashboard."""

    model_config = ConfigDict(extra="forbid")

    operation: str
    provider: str
    model: str
    status: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    http_status: int | None
    request_id: str | None
    error_code: str | None
    scan_id: UUID | None
    created_at: datetime


class AIUsageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    errors: int


class AIUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: AIUsageSummary
    data: list[AIUsageEntry]


class ProviderAIChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: AIText
    uncertainties: Annotated[list[AIShortText], Field(max_length=10)]
    referenced_finding_refs: Annotated[list[FindingReference], Field(max_length=15)]


class AIRecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["immediate", "high", "medium", "low"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: AIShortText
    related_finding_ids: Annotated[list[UUID], Field(max_length=15)]


class AIProviderRecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["immediate", "high", "medium", "low"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: AIShortText
    related_finding_refs: Annotated[list[FindingReference], Field(max_length=15)]


class AIFindingExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    why_it_matters: AIShortText
    plain_language_explanation: AIShortText
    recommendation: AIShortText
    evidence_used: Annotated[list[AIShortText], Field(max_length=10)]
    uncertainty: Annotated[str | None, Field(max_length=1000)]


class AIProviderFindingExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_ref: FindingReference
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


class ProviderScanAIAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: AIText
    overall_assessment: AIText
    plain_language_summary: AIText
    priority_actions: Annotated[
        list[AIProviderRecommendedAction], Field(max_length=15)
    ]
    important_findings: Annotated[
        list[AIProviderFindingExplanation], Field(max_length=15)
    ]
    uncertainties: Annotated[list[AIShortText], Field(max_length=20)]


class ProviderScanAIChildAnalysis(BaseModel):
    """Structured result for one bounded finding chunk."""

    model_config = ConfigDict(extra="forbid")

    priority_actions: Annotated[
        list[AIProviderRecommendedAction], Field(max_length=15)
    ]
    important_findings: Annotated[
        list[AIProviderFindingExplanation], Field(max_length=15)
    ]
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
    language: AILanguage = "en"
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
