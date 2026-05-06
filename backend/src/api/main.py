from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from api.core.config import get_settings
from api.db.session import get_session, init_db
from api.models.persistence import (
    ArtifactRecord,
    CPERecord,
    DeviceRecord,
    EnrichmentJobRecord,
    FindingRecord,
    PortRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas import (
    PersistedFinding,
    PersistedScanDetail,
    PersistedScanSummary,
    ScanIngestResponse,
    ScanResult,
)
from api.schemas.persistence import (
    EnrichmentJobView,
    PersistedArtifact,
    PersistedDevice,
    PersistedPort,
    PersistedService,
)
from api.services.enrichment import process_pending_enrichment_jobs
from api.services.persistence import persist_scan

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    init_db()
    yield


app = FastAPI(
    title="Vulnerability Scanner Backend",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Health probe")
@app.get("/api/v1/health", summary="Health probe")
def read_health() -> dict[str, str]:
    """Simple endpoint used for uptime checks."""

    return {"status": "ok"}


def ingest_scan(scan: ScanResult, session: Session) -> ScanIngestResponse:
    """Accept scan payloads from the hardware agent."""

    record = persist_scan(session, scan)
    return ScanIngestResponse(
        message="scan received successfully",
        scan_id=record.scan_id,
        devices_received=len(scan.devices),
    )


@app.post(
    "/scans",
    summary="Receive scan payloads",
    response_model=ScanIngestResponse,
)
@app.post(
    "/api/v1/scans",
    summary="Receive scan payloads",
    response_model=ScanIngestResponse,
)
def ingest_scan_endpoint(
    scan: ScanResult,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> ScanIngestResponse:
    """HTTP wrapper for scan ingestion."""

    response = ingest_scan(scan, session)
    if settings.process_enrichment_inline:
        background_tasks.add_task(_process_enrichment_jobs)
    return response


@app.get("/scans", response_model=list[PersistedScanSummary])
@app.get("/api/v1/scans", response_model=list[PersistedScanSummary])
def list_scans(session: Session = Depends(get_session)) -> list[PersistedScanSummary]:
    scans = session.exec(select(ScanRecord).order_by(ScanRecord.timestamp.desc())).all()
    summaries: list[PersistedScanSummary] = []
    for scan in scans:
        device_count = len(
            session.exec(
                select(DeviceRecord).where(DeviceRecord.scan_id == scan.scan_id)
            ).all()
        )
        finding_count = len(
            session.exec(
                select(FindingRecord).where(FindingRecord.scan_id == scan.scan_id)
            ).all()
        )
        summaries.append(
            PersistedScanSummary(
                scan_id=scan.scan_id,
                timestamp=scan.timestamp,
                subnet=scan.subnet,
                target_mode=scan.target_mode,
                scan_profile=scan.scan_profile,
                device_count=device_count,
                finding_count=finding_count,
            )
        )
    return summaries


@app.get("/scans/{scan_id}", response_model=PersistedScanDetail)
@app.get("/api/v1/scans/{scan_id}", response_model=PersistedScanDetail)
def get_scan(
    scan_id: str,
    session: Session = Depends(get_session),
) -> PersistedScanDetail:
    scan = session.get(ScanRecord, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return _serialize_scan_detail(session, scan)


@app.get("/findings", response_model=list[PersistedFinding])
@app.get("/api/v1/findings", response_model=list[PersistedFinding])
def list_findings(
    severity: str | None = None,
    scan_id: str | None = None,
    device_ip: str | None = None,
    session: Session = Depends(get_session),
) -> list[PersistedFinding]:
    statement = select(FindingRecord)
    if severity is not None:
        statement = statement.where(FindingRecord.severity == severity)
    if scan_id is not None:
        statement = statement.where(FindingRecord.scan_id == scan_id)
    if device_ip is not None:
        statement = statement.where(FindingRecord.ip == device_ip)
    findings = session.exec(statement.order_by(FindingRecord.created_at.desc())).all()
    return [_serialize_finding(record) for record in findings]


def _process_enrichment_jobs() -> None:
    for session in get_session():
        process_pending_enrichment_jobs(session)


def _serialize_scan_detail(session: Session, scan: ScanRecord) -> PersistedScanDetail:
    devices = session.exec(
        select(DeviceRecord).where(DeviceRecord.scan_id == scan.scan_id)
    ).all()
    artifacts = session.exec(
        select(ArtifactRecord).where(ArtifactRecord.scan_id == scan.scan_id)
    ).all()
    findings = session.exec(
        select(FindingRecord).where(FindingRecord.scan_id == scan.scan_id)
    ).all()
    jobs = session.exec(
        select(EnrichmentJobRecord).where(EnrichmentJobRecord.scan_id == scan.scan_id)
    ).all()
    return PersistedScanDetail(
        scan_id=scan.scan_id,
        timestamp=scan.timestamp,
        subnet=scan.subnet,
        target_mode=scan.target_mode,
        scan_profile=scan.scan_profile,
        metadata=scan.metadata_json,
        devices=[_serialize_device(session, device) for device in devices],
        findings=[_serialize_finding(record) for record in findings],
        artifacts=[
            PersistedArtifact(
                kind=artifact.kind,
                path=artifact.path,
                stage=artifact.stage,
                host_ip=artifact.host_ip,
            )
            for artifact in artifacts
        ],
        enrichment_jobs=[
            EnrichmentJobView.model_validate(job, from_attributes=True) for job in jobs
        ],
    )


def _serialize_device(session: Session, device: DeviceRecord) -> PersistedDevice:
    ports = session.exec(
        select(PortRecord).where(PortRecord.device_id == device.id)
    ).all()
    serialized_ports: list[PersistedPort] = []
    for port in ports:
        service = session.exec(
            select(ServiceRecord).where(ServiceRecord.port_id == port.id)
        ).first()
        cpes = session.exec(select(CPERecord).where(CPERecord.port_id == port.id)).all()
        serialized_ports.append(
            PersistedPort(
                port=port.port,
                protocol=port.protocol,
                state=port.state,
                service=PersistedService(
                    name=service.name if service is not None else "unknown",
                    version=service.version if service is not None else None,
                    cpes=[record.cpe for record in cpes],
                ),
            )
        )
    return PersistedDevice(
        id=device.id or 0,
        ip=device.ip,
        mac=device.mac,
        hostname=device.hostname,
        vendor=device.vendor,
        ports=serialized_ports,
    )


def _serialize_finding(record: FindingRecord) -> PersistedFinding:
    return PersistedFinding(
        id=record.id or 0,
        scan_id=record.scan_id,
        ip=record.ip,
        port=record.port,
        protocol=record.protocol,
        service=record.service,
        source=record.source,
        source_script=record.source_script,
        cve_id=record.cve_id,
        cvss_score=record.cvss_score,
        severity=record.severity,
        confidence=record.confidence,
        title=record.title,
        description=record.description,
        recommendation=record.recommendation,
        evidence=record.evidence,
        references=record.references_json,
        source_labels=record.source_labels_json,
    )
