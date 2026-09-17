from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ReportKind = Literal["explained", "technical"]


class ScanReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    kind: ReportKind
    generated_at: datetime
    filename: str
    content_type: Literal["application/json"]
    sections: dict[str, Any]
