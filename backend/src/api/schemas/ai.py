from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from api.services.ai.schemas import ScanAIAnalysis

AIAnalysisReadStatus = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
    "unavailable",
]


class ScanAIAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    analysis_id: UUID | None
    status: AIAnalysisReadStatus
    analysis: ScanAIAnalysis | None
    provider: str | None
    model: str | None
    context_version: str | None
    prompt_version: str | None
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None

    @model_validator(mode="after")
    def completed_requires_analysis(self) -> "ScanAIAnalysisResponse":
        if self.status == "completed" and self.analysis is None:
            raise ValueError("completed analysis requires a payload")
        if self.status != "completed" and self.analysis is not None:
            raise ValueError("only a completed analysis may expose a payload")
        return self
