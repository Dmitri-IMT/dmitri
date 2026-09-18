from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from api.core.severity import SEVERITY_ORDER

_FINDING_SEVERITY_CHECK = (
    "severity IN (" + ", ".join(f"'{k}'" for k in SEVERITY_ORDER) + ")"
)
AI_ANALYSIS_STATUSES = ("pending", "processing", "completed", "failed")
_AI_ANALYSIS_STATUS_CHECK = (
    "status IN (" + ", ".join(f"'{status}'" for status in AI_ANALYSIS_STATUSES) + ")"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Every datetime the application stores comes from utc_now() and is therefore
# timezone-aware. Columns must be timestamptz to round-trip that: psycopg returns
# naive datetimes from a plain `timestamp` column, and comparing one against
# utc_now() raises "can't compare offset-naive and offset-aware datetimes".
UTC_TIMESTAMP = DateTime(timezone=True)


class ScanRecord(SQLModel, table=True):
    __tablename__ = "scans"

    scan_id: UUID = Field(primary_key=True)
    org_id: UUID | None = Field(default=None, foreign_key="orgs.id", index=True)
    agent_id: UUID | None = Field(default=None, foreign_key="agents.id")
    timestamp: datetime = Field(sa_type=UTC_TIMESTAMP)
    subnet: str
    scan_mode: str
    status: str = Field(default="completed")
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


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
    operating_system_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


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
    machine_type: str | None = None
    operating_system_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    open_ports_count: int
    highest_severity: str | None = None
    vulnerability_count: int = Field(
        default=0, sa_column_kwargs={"server_default": "0"}
    )
    first_seen_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    last_seen_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class PortRecord(SQLModel, table=True):
    __tablename__ = "ports"
    __table_args__ = (UniqueConstraint("scan_host_id", "port", "protocol"),)

    id: int | None = Field(default=None, primary_key=True)
    scan_host_id: int = Field(index=True, foreign_key="scan_hosts.id")
    port: int
    protocol: str
    state: str
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class HostPortRecord(SQLModel, table=True):
    __tablename__ = "host_ports"
    __table_args__ = (UniqueConstraint("host_id", "port", "protocol"),)

    id: int | None = Field(default=None, primary_key=True)
    host_id: UUID = Field(index=True, foreign_key="hosts.id")
    port: int
    protocol: str
    service: str
    version: str | None = None
    first_seen_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    last_seen_at: datetime = Field(sa_type=UTC_TIMESTAMP)


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



class IndustrialServiceRecord(SQLModel, table=True):
    __tablename__ = "industrial_services"
    __table_args__ = (
        UniqueConstraint("scan_host_id", "protocol", "port"),
        CheckConstraint(
            "protocol IN ('modbus_tcp')", name="ck_industrial_services_protocol"
        ),
        CheckConstraint(
            "confidence IN ('suspected', 'confirmed')",
            name="ck_industrial_services_confidence",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_host_id: int = Field(index=True, foreign_key="scan_hosts.id")
    port_id: int | None = Field(default=None, index=True, foreign_key="ports.id")
    protocol: str
    port: int
    confidence: str
    mapping_source: str | None = None
    evidence_sources_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    write_requests_sent: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class ModbusUnitRecord(SQLModel, table=True):
    __tablename__ = "modbus_units"
    __table_args__ = (
        UniqueConstraint("industrial_service_id", "unit_id"),
        CheckConstraint(
            "status IN ('responding', 'exception', 'timeout', 'error', 'skipped')",
            name="ck_modbus_units_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    industrial_service_id: int = Field(
        index=True, foreign_key="industrial_services.id"
    )
    unit_id: int
    status: str
    exception_code: int | None = None
    error: str | None = None
    identification_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    identification_sources_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    address_ranges_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class FindingRecord(SQLModel, table=True):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("scan_id", "dedupe_key"),
        CheckConstraint(_FINDING_SEVERITY_CHECK, name="ck_findings_severity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    finding_id: UUID = Field(default_factory=uuid4, unique=True, index=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    scan_host_id: int | None = Field(
        default=None, index=True, foreign_key="scan_hosts.id"
    )
    port_id: int | None = Field(default=None, index=True, foreign_key="ports.id")
    modbus_unit_id: int | None = Field(
        default=None, index=True, foreign_key="modbus_units.id"
    )
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
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class HostFindingRecord(SQLModel, table=True):
    __tablename__ = "host_findings"
    __table_args__ = (UniqueConstraint("host_id", "dedupe_key"),)

    id: int | None = Field(default=None, primary_key=True)
    host_id: UUID = Field(index=True, foreign_key="hosts.id")
    dedupe_key: str = Field(index=True)
    first_seen_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    last_seen_at: datetime = Field(sa_type=UTC_TIMESTAMP)
    fixed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)


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
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    started_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    next_attempt_at: datetime | None = Field(
        default=None, index=True, sa_type=UTC_TIMESTAMP
    )
    completed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)


class NvdCacheRecord(SQLModel, table=True):
    __tablename__ = "nvd_cache"

    id: int | None = Field(default=None, primary_key=True)
    query_key: str = Field(unique=True, index=True)
    query_kind: str = Field(index=True)
    query_value: str
    response_json: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    expires_at: datetime = Field(index=True, sa_type=UTC_TIMESTAMP)


class KevRecord(SQLModel, table=True):
    __tablename__ = "kev_records"

    cve_id: str = Field(primary_key=True)
    date_added: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    known_ransomware: bool = Field(default=False)
    required_action: str | None = None
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class EpssRecord(SQLModel, table=True):
    __tablename__ = "epss_records"

    cve_id: str = Field(primary_key=True)
    epss_score: float
    percentile: float | None = None
    scored_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class KevCacheRecord(SQLModel, table=True):
    __tablename__ = "kev_cache"

    cve_id: str = Field(primary_key=True)
    response_json: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    expires_at: datetime = Field(index=True, sa_type=UTC_TIMESTAMP)


class EpssCacheRecord(SQLModel, table=True):
    __tablename__ = "epss_cache"

    cve_id: str = Field(primary_key=True)
    response_json: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    expires_at: datetime = Field(index=True, sa_type=UTC_TIMESTAMP)


class RiskSnapshotRecord(SQLModel, table=True):
    __tablename__ = "risk_snapshots"
    __table_args__ = (UniqueConstraint("finding_id"),)

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(index=True, foreign_key="findings.id")
    confidence: str
    exploitability: float
    risk_score: float
    rationale: str
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)


class AIScanAnalysisRecord(SQLModel, table=True):
    __tablename__ = "ai_scan_analyses"
    __table_args__ = (
        UniqueConstraint("scan_id"),
        CheckConstraint(_AI_ANALYSIS_STATUS_CHECK, name="ck_ai_scan_analyses_status"),
        CheckConstraint(
            "status != 'completed' OR analysis_json IS NOT NULL",
            name="ck_ai_scan_analyses_completed_payload",
        ),
        CheckConstraint("attempts >= 0", name="ck_ai_scan_analyses_attempts"),
    )

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: UUID = Field(default_factory=uuid4, unique=True, index=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    provider: str
    model: str
    status: str = Field(default="pending", index=True)
    analysis_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
    )
    context_version: str
    prompt_version: str
    writing_skill_version: str = "1"
    analyzed_findings: int = 0
    failed_findings: int = 0
    total_findings: int = 0
    context_hash: str | None = None
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
    started_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    next_attempt_at: datetime | None = Field(
        default=None, index=True, sa_type=UTC_TIMESTAMP
    )
    completed_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=UTC_TIMESTAMP,
        sa_column_kwargs={"onupdate": utc_now},
    )


class AIChatMessageRecord(SQLModel, table=True):
    __tablename__ = "ai_chat_messages"

    message_id: UUID = Field(default_factory=uuid4, primary_key=True)
    scan_id: UUID = Field(index=True, foreign_key="scans.scan_id")
    user_id: UUID = Field(index=True, foreign_key="users.id")
    question: str
    answer: str
    uncertainties_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    referenced_finding_ids_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTC_TIMESTAMP)
