from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from api.core.config import get_settings
from api.db.session import get_session, init_db
from api.models.persistence import (
    ArtifactRecord,
    CPERecord,
    DeviceRecord,
    EnrichmentJobRecord,
    EpssRecord,
    FindingRecord,
    KevRecord,
    PortRecord,
    RiskSnapshotRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas import (
    PersistedFinding,
    PersistedScanDetail,
    PersistedScanRiskSummary,
    PersistedScanSummary,
    ScanIngestResponse,
    ScanResult,
)
from api.schemas.persistence import (
    EnrichmentJobView,
    EpssRecordView,
    KevRecordView,
    PersistedArtifact,
    PersistedDevice,
    PersistedPort,
    PersistedService,
    RiskSnapshotView,
)
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
    session: Session = Depends(get_session),
) -> ScanIngestResponse:
    """HTTP wrapper for scan ingestion."""

    return ingest_scan(scan, session)


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
    scan_id: UUID,
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
    return [_serialize_finding(session, record) for record in findings]


@app.get("/findings/{finding_id}", response_model=PersistedFinding)
@app.get("/api/v1/findings/{finding_id}", response_model=PersistedFinding)
def get_finding(
    finding_id: int,
    session: Session = Depends(get_session),
) -> PersistedFinding:
    finding = session.get(FindingRecord, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    return _serialize_finding(session, finding)


@app.get(
    "/scans/{scan_id}/risk-summary",
    response_model=PersistedScanRiskSummary,
)
@app.get(
    "/api/v1/scans/{scan_id}/risk-summary",
    response_model=PersistedScanRiskSummary,
)
def get_scan_risk_summary(
    scan_id: UUID,
    session: Session = Depends(get_session),
) -> PersistedScanRiskSummary:
    scan = session.get(ScanRecord, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")

    findings = session.exec(
        select(FindingRecord).where(FindingRecord.scan_id == scan_id)
    ).all()
    serialized_findings = [_serialize_finding(session, record) for record in findings]
    risk_scores = [
        finding.risk.risk_score
        for finding in serialized_findings
        if finding.risk is not None
    ]
    kev_findings = [
        finding for finding in serialized_findings if finding.kev is not None
    ]
    confirmed_findings = [
        finding for finding in serialized_findings if finding.confidence == "confirmed"
    ]
    top_findings = sorted(
        serialized_findings,
        key=lambda finding: (
            finding.risk.risk_score if finding.risk is not None else 0.0
        ),
        reverse=True,
    )[:5]
    average_risk_score = (
        round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0
    )
    return PersistedScanRiskSummary(
        scan_id=scan_id,
        total_findings=len(serialized_findings),
        confirmed_findings=len(confirmed_findings),
        kev_findings=len(kev_findings),
        average_risk_score=average_risk_score,
        max_risk_score=max(risk_scores) if risk_scores else 0.0,
        top_findings=top_findings,
    )


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
        findings=[_serialize_finding(session, record) for record in findings],
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


def _serialize_finding(session: Session, record: FindingRecord) -> PersistedFinding:
    kev = _get_kev_view(session, record)
    epss = _get_epss_view(session, record)
    risk = _get_risk_view(session, record)
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
        kev=kev,
        epss=epss,
        risk=risk,
    )


def _get_kev_view(session: Session, record: FindingRecord) -> KevRecordView | None:
    if record.cve_id is None:
        return None
    kev_record = session.get(KevRecord, record.cve_id.upper())
    if kev_record is None:
        return None
    return KevRecordView(
        cve_id=kev_record.cve_id,
        date_added=kev_record.date_added,
        known_ransomware=kev_record.known_ransomware,
        required_action=kev_record.required_action,
    )


def _get_epss_view(session: Session, record: FindingRecord) -> EpssRecordView | None:
    if record.cve_id is None:
        return None
    epss_record = session.get(EpssRecord, record.cve_id.upper())
    if epss_record is None:
        return None
    return EpssRecordView(
        cve_id=epss_record.cve_id,
        epss_score=epss_record.epss_score,
        percentile=epss_record.percentile,
        scored_at=epss_record.scored_at,
    )


def _get_risk_view(session: Session, record: FindingRecord) -> RiskSnapshotView | None:
    if record.id is None:
        return None
    risk_record = session.exec(
        select(RiskSnapshotRecord).where(RiskSnapshotRecord.finding_id == record.id)
    ).first()
    if risk_record is None:
        return None
    return RiskSnapshotView(
        confidence=risk_record.confidence,
        exploitability=risk_record.exploitability,
        risk_score=risk_record.risk_score,
        rationale=risk_record.rationale,
    )
