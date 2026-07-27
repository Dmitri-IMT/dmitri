from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, func, select

from api.models.persistence import (
    FindingRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas.read import (
    FindingListResponse,
    FindingRead,
    HostDetailResponse,
    HostListResponse,
    HostScanHistoryEntry,
    HostSummary,
    Port,
    ScanDetailResponse,
    ScanHostView,
)
from api.services.hosts import highest_severity, open_ports_count


def list_hosts(
    session: Session, *, org_id: UUID, page: int = 1, per_page: int = 20
) -> HostListResponse:
    total = session.exec(
        select(func.count())
        .select_from(HostRecord)
        .where(HostRecord.org_id == org_id)
    ).one()
    hosts = session.exec(
        select(HostRecord)
        .where(HostRecord.org_id == org_id)
        .order_by(HostRecord.last_seen_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    return HostListResponse(
        data=[_to_host_summary(host) for host in hosts],
        total=total,
        page=page,
    )


def get_host_detail(
    session: Session, host_id: UUID, *, org_id: UUID
) -> HostDetailResponse | None:
    host = session.exec(
        select(HostRecord).where(
            HostRecord.id == host_id, HostRecord.org_id == org_id
        )
    ).first()
    if host is None:
        return None

    latest_scan_host = session.exec(
        select(ScanHostRecord)
        .join(ScanRecord, ScanHostRecord.scan_id == ScanRecord.scan_id)
        .where(ScanHostRecord.host_id == host_id)
        .where(ScanRecord.org_id == org_id)
        .order_by(ScanRecord.timestamp.desc())
    ).first()
    ports = (
        _ports_for_scan_host(session, latest_scan_host.id) if latest_scan_host else []
    )

    scan_history_rows = session.exec(
        select(ScanHostRecord, ScanRecord)
        .join(ScanRecord, ScanHostRecord.scan_id == ScanRecord.scan_id)
        .where(ScanHostRecord.host_id == host_id)
        .where(ScanRecord.org_id == org_id)
        .order_by(ScanRecord.timestamp.desc())
    ).all()
    scan_history = [
        HostScanHistoryEntry(
            scan_id=scan.scan_id,
            timestamp=scan.timestamp,
            scan_mode=scan.scan_mode,
            open_ports_count=open_ports_count(session, scan_host.id),
            highest_severity=highest_severity(session, scan_host.id),
        )
        for scan_host, scan in scan_history_rows
    ]

    return HostDetailResponse(
        host_id=host.id,
        ip=host.ip,
        mac=host.mac,
        hostname=host.hostname,
        vendor=host.vendor,
        first_seen_at=host.first_seen_at,
        last_seen_at=host.last_seen_at,
        open_ports_count=host.open_ports_count,
        highest_severity=host.highest_severity,
        ports=ports,
        scan_history=scan_history,
    )


def get_scan_detail(
    session: Session, scan_id: UUID, *, org_id: UUID
) -> ScanDetailResponse | None:
    scan = session.exec(
        select(ScanRecord).where(
            ScanRecord.scan_id == scan_id, ScanRecord.org_id == org_id
        )
    ).first()
    if scan is None:
        return None

    scan_hosts = session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
    ).all()
    hosts = [
        ScanHostView(
            host_id=scan_host.host_id,
            ip=scan_host.ip,
            mac=scan_host.mac,
            hostname=scan_host.hostname,
            vendor=scan_host.vendor,
            ports=_ports_for_scan_host(session, scan_host.id),
        )
        for scan_host in scan_hosts
    ]

    finding_rows = session.exec(
        select(FindingRecord, ScanHostRecord.host_id)
        .outerjoin(ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id)
        .where(FindingRecord.scan_id == scan_id)
    ).all()
    findings = [_to_finding_read(finding, host_id) for finding, host_id in finding_rows]

    return ScanDetailResponse(
        scan_id=scan.scan_id,
        timestamp=scan.timestamp,
        subnet=scan.subnet,
        scan_mode=scan.scan_mode,
        hosts=hosts,
        findings=findings,
        metadata=scan.metadata_json,
        status=scan.status,
        command_id=None,
        host_count=len(hosts),
        finding_count=len(findings),
    )


def list_findings(
    session: Session,
    *,
    org_id: UUID,
    host_id: UUID | None = None,
    page: int = 1,
    per_page: int = 20,
) -> FindingListResponse:
    base = (
        select(FindingRecord, ScanHostRecord.host_id)
        .join(ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id)
        .where(ScanRecord.org_id == org_id)
    )
    if host_id is not None:
        base = base.join(
            ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id
        ).where(ScanHostRecord.host_id == host_id)
    else:
        base = base.outerjoin(
            ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id
        )

    total = session.exec(
        select(func.count()).select_from(base.subquery())
    ).one()
    rows = session.exec(
        base.offset((page - 1) * per_page).limit(per_page)
    ).all()

    return FindingListResponse(
        data=[_to_finding_read(finding, resolved) for finding, resolved in rows],
        total=total,
        page=page,
    )


def _ports_for_scan_host(session: Session, scan_host_id: int | None) -> list[Port]:
    port_records = session.exec(
        select(PortRecord).where(PortRecord.scan_host_id == scan_host_id)
    ).all()
    ports = []
    for port_record in port_records:
        service = session.exec(
            select(ServiceRecord).where(ServiceRecord.port_id == port_record.id)
        ).first()
        ports.append(
            Port(
                port=port_record.port,
                protocol=port_record.protocol,
                state=port_record.state,
                service=service.name if service else "unknown",
                version=service.version if service else None,
            )
        )
    return ports


def _to_host_summary(host: HostRecord) -> HostSummary:
    return HostSummary(
        host_id=host.id,
        ip=host.ip,
        mac=host.mac,
        hostname=host.hostname,
        vendor=host.vendor,
        first_seen_at=host.first_seen_at,
        last_seen_at=host.last_seen_at,
        open_ports_count=host.open_ports_count,
        highest_severity=host.highest_severity,
    )


def _to_finding_read(finding: FindingRecord, host_id: UUID | None) -> FindingRead:
    return FindingRead(
        finding_id=finding.finding_id,
        scan_id=finding.scan_id,
        host_id=host_id,
        host_ip=finding.ip,
        port=finding.port,
        protocol=finding.protocol,
        service=finding.service,
        source=finding.source,
        source_script=finding.source_script,
        cve_id=finding.cve_id,
        cvss_score=finding.cvss_score,
        severity=finding.severity,
        title=finding.title,
        description=finding.description,
        recommendation=finding.recommendation,
        evidence=finding.evidence,
        references=finding.references_json,
        detected_at=finding.created_at,
    )
