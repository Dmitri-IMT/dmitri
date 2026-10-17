from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ScanDeletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: int
    skipped: int
    machines_removed: int


class HostDeletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: int
