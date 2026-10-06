from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ProgressStage = Literal[
    "discovery",
    "ports",
    "deep_inspection",
    "ot_inspection",
    "targeted_assessment",
    "normalization",
    "uploading",
]


class ScanProgressSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: ProgressStage
    percent: Annotated[int, Field(ge=0, le=99)]
    machines: Annotated[int | None, Field(ge=0)]
    open_ports: Annotated[int | None, Field(ge=0)]
    filtered_ports: Annotated[int | None, Field(ge=0)]
    industrial_services: Annotated[int | None, Field(ge=0)]
    vulnerabilities: Annotated[int | None, Field(ge=0)]


class ScanProgressRead(ScanProgressSnapshot):
    updated_at: datetime
