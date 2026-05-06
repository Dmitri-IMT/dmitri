from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PersistedService(BaseModel):
    name: str
    version: str | None = None
    cpes: list[str]


class PersistedPort(BaseModel):
    port: int
    protocol: str
    state: str
    service: PersistedService


class PersistedDevice(BaseModel):
    id: int
    ip: str
    mac: str | None
    hostname: str
    vendor: str
    ports: list[PersistedPort]


class PersistedFinding(BaseModel):
    id: int
    scan_id: UUID
    ip: str | None
    port: int | None
    protocol: str | None
    service: str | None
    source: str | None
    source_script: str | None
    cve_id: str | None
    cvss_score: float | None
    severity: str
    confidence: str
    title: str
    description: str
    recommendation: str
    evidence: str
    references: list[str]
    source_labels: list[str]


class PersistedArtifact(BaseModel):
    kind: str
    path: str
    stage: str
    host_ip: str | None


class EnrichmentJobView(BaseModel):
    id: int
    scan_id: UUID
    port_id: int | None
    finding_id: int | None
    job_type: str
    target_value: str
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class PersistedScanSummary(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: str
    target_mode: str
    scan_profile: str
    device_count: int
    finding_count: int


class PersistedScanDetail(BaseModel):
    scan_id: UUID
    timestamp: datetime
    subnet: str
    target_mode: str
    scan_profile: str
    metadata: dict[str, str | int | float | bool] | None
    devices: list[PersistedDevice]
    findings: list[PersistedFinding]
    artifacts: list[PersistedArtifact]
    enrichment_jobs: list[EnrichmentJobView]
