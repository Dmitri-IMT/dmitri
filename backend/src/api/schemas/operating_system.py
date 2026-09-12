"""Operating-system evidence shared by scan ingest and read schemas."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, constr


class OperatingSystemDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: constr(min_length=1)
    accuracy: Annotated[int, Field(ge=0, le=100, strict=True)]
    vendor: str | None = None
    family: str | None = None
    generation: str | None = None
    device_type: str | None = None
    cpes: list[constr(min_length=1)] = Field(
        default_factory=list, json_schema_extra={"default": []}
    )
