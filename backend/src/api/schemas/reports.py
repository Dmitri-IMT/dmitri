from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from api.schemas.ai import AILanguage

ReportKind = Literal["explained", "technical"]


class ScanReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    kind: ReportKind
    language: AILanguage = "en"
    generated_at: datetime
    filename: str
    content_type: Literal["application/pdf"]
    sections: dict[str, Any]
