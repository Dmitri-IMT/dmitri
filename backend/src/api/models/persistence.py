from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanRecord(SQLModel, table=True):
    __tablename__ = "scans"

    scan_id: UUID = Field(primary_key=True)
    org_id: UUID | None = Field(default=None, foreign_key="orgs.id", index=True)
    timestamp: datetime
    subnet: str
    scan_mode: str
    status: str = Field(default="completed")
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class ArtifactRecord(SQLModel, table=True):
    __tablename__ = "artifacts"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    kind: str
    path: str
    stage: str
    host_ip: str | None = None


class ScanHostRecord(SQLModel, table=True):
    __tablename__ = "scan_hosts"
    __table_args__ = (UniqueConstraint("scan_id", "ip"),)

    id: int | None = Field(default=None, primary_key=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    host_id: UUID | None = Field(default=None, index=True, foreign_key="hosts.id")
    ip: str = Field(index=True)
    mac: str | None = None
    hostname: str
    vendor: str
    created_at: datetime = Field(default_factory=utc_now)


class HostRecord(SQLModel, table=True):
    __tablename__ = "hosts"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "identity_key", postgresql_nulls_not_distinct=True
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID | None = Field(default=None, foreign_key="orgs.id", index=True)
    identity_key: str = Field(index=True)
    ip: str
    mac: str | None = None
    hostname: str
    vendor: str
    open_ports_count: int
    highest_severity: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PortRecord(SQLModel, table=True):
    __tablename__ = "ports"
    __table_args__ = (UniqueConstraint("scan_host_id", "port", "protocol"),)

    id: int | None = Field(default=None, primary_key=True)
    scan_host_id: int = Field(index=True, foreign_key="scan_hosts.id")
    port: int
    protocol: str
    state: str
    created_at: datetime = Field(default_factory=utc_now)


class ServiceRecord(SQLModel, table=True):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("port_id"),)

    id: int | None = Field(default=None, primary_key=True)
    port_id: int = Field(index=True, foreign_key="ports.id")
    name: str
    version: str | None = None


class CPERecord(SQLModel, table=True):
    __tablename__ = "cpes"
    __table_args__ = (UniqueConstraint("port_id", "cpe"),)

    id: int | None = Field(default=None, primary_key=True)
    port_id: int = Field(index=True, foreign_key="ports.id")
    cpe: str = Field(index=True)


class FindingRecord(SQLModel, table=True):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("scan_id", "dedupe_key"),)

    id: int | None = Field(default=None, primary_key=True)
    finding_id: UUID = Field(default_factory=uuid4, unique=True, index=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    scan_host_id: int | None = Field(
        default=None, index=True, foreign_key="scan_hosts.id"
    )
    port_id: int | None = Field(default=None, index=True, foreign_key="ports.id")
    ip: str | None = Field(default=None, index=True)
    port: int | None = None
    protocol: str | None = None
    service: str | None = None
    source: str | None = None
    source_script: str | None = None
    cve_id: str | None = Field(default=None, index=True)
    cvss_score: float | None = None
    severity: str
    confidence: str = Field(default="tentative", index=True)
    title: str
    description: str
    recommendation: str
    evidence: str
    references_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_labels_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    dedupe_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EnrichmentJobRecord(SQLModel, table=True):
    __tablename__ = "enrichment_jobs"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    port_id: int | None = Field(default=None, foreign_key="ports.id")
    finding_id: int | None = Field(default=None, foreign_key="findings.id")
    job_type: str = Field(index=True)
    target_value: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    attempts: int = Field(default=0)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class NvdCacheRecord(SQLModel, table=True):
    __tablename__ = "nvd_cache"

    id: int | None = Field(default=None, primary_key=True)
    query_key: str = Field(unique=True, index=True)
    query_kind: str = Field(index=True)
    query_value: str
    response_json: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(index=True)


class KevRecord(SQLModel, table=True):
    __tablename__ = "kev_records"

    cve_id: str = Field(primary_key=True)
    date_added: datetime | None = None
    known_ransomware: bool = Field(default=False)
    required_action: str | None = None
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EpssRecord(SQLModel, table=True):
    __tablename__ = "epss_records"

    cve_id: str = Field(primary_key=True)
    epss_score: float
    percentile: float | None = None
    scored_at: datetime | None = None
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KevCacheRecord(SQLModel, table=True):
    __tablename__ = "kev_cache"

    cve_id: str = Field(primary_key=True)
    response_json: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(index=True)


class EpssCacheRecord(SQLModel, table=True):
    __tablename__ = "epss_cache"

    cve_id: str = Field(primary_key=True)
    response_json: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(index=True)


class RiskSnapshotRecord(SQLModel, table=True):
    __tablename__ = "risk_snapshots"
    __table_args__ = (UniqueConstraint("finding_id"),)

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(index=True, foreign_key="findings.id")
    confidence: str
    exploitability: float
    risk_score: float
    rationale: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
