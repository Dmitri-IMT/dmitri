from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, cast
from sqlalchemy.dialects.postgresql import INET
from sqlmodel import Session, func, select

from api.core.error_codes import scan_error_code
from api.core.scan_read import scan_duration_seconds
from api.core.severity import SEVERITY_ORDER, Severity
from api.models.command import Agent
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    KevRecord,
    PortRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas.operating_system import OperatingSystemDetection
from api.schemas.read import (
    FindingListResponse,
    FindingRead,
    HostDetailResponse,
    HostListResponse,
    HostScanHistoryEntry,
    HostSortBy,
    HostSummary,
    Port,
    ScanDetailResponse,
    ScanHostView,
    ScanListResponse,
    ScanRiskSummaryResponse,
    ScanSortBy,
    ScanStatus,
    ScanSummary,
    SeverityBreakdown,
    SortOrder,
)
from api.schemas.scan import ModbusTcpServicePayload
from api.services import commands
from api.services.hosts import highest_severity, open_ports_count

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20

_SCAN_SORT_COLUMNS = {
    "timestamp": ScanRecord.timestamp,
    "status": ScanRecord.status,
    "scan_mode": ScanRecord.scan_mode,
}
_HOST_SORT_COLUMNS = {
    "last_seen_at": HostRecord.last_seen_at,
    "hostname": HostRecord.hostname,
    "vendor": HostRecord.vendor,
    "ip": cast(HostRecord.ip, INET),
}
_SEVERITY_RANK = case(SEVERITY_ORDER, value=FindingRecord.severity, else_=0)
_SEVERITY_RANK_TO_LABEL = {rank: label for label, rank in SEVERITY_ORDER.items()}


def list_hosts(
    session: Session,
    *,
    org_id: UUID,
    page: int = DEFAULT_PAGE,
    per_page: int = DEFAULT_PER_PAGE,
    sort_by: HostSortBy = "last_seen_at",
    sort_order: SortOrder = "desc",
) -> HostListResponse:
    total = session.exec(
        select(func.count())
        .select_from(HostRecord)
        .where(HostRecord.org_id == org_id)
    ).one()
    column = _HOST_SORT_COLUMNS[sort_by]
    direction = column.desc() if sort_order == "desc" else column.asc()
    hosts = session.exec(
        select(HostRecord)
        .where(HostRecord.org_id == org_id)
        .order_by(direction, HostRecord.id.asc())
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
            operating_system=_to_operating_system(scan_host.operating_system_json),
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
        operating_system=_to_operating_system(host.operating_system_json),
        industrial_services=_to_industrial_services(
            host.industrial_services_json
        ),
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
            operating_system=_to_operating_system(
                scan_host.operating_system_json
            ),
            industrial_services=_to_industrial_services(
                scan_host.industrial_services_json
            ),
            ports=_ports_for_scan_host(session, scan_host.id),
        )
        for scan_host in scan_hosts
    ]

    finding_rows = session.exec(
        select(FindingRecord, ScanHostRecord.host_id)
        .outerjoin(ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id)
        .where(FindingRecord.scan_id == scan_id)
    ).all()
    findings = findings_with_risk(session, finding_rows)

    command = commands.command_for_scan(session, scan_id)
    agent = session.get(Agent, scan.agent_id) if scan.agent_id else None
    return ScanDetailResponse(
        scan_id=scan.scan_id,
        timestamp=scan.timestamp,
        subnet=scan.subnet,
        scan_mode=scan.scan_mode,
        hosts=hosts,
        findings=findings,
        metadata=scan.metadata_json,
        status=scan.status,
        command_id=command.id if command else None,
        error_code=scan_error_code(
            scan.status, command.error_code if command else None
        ),
        host_count=len(hosts),
        finding_count=len(findings),
        agent_id=scan.agent_id,
        box_name=agent.display_name if agent is not None else None,
        duration=scan_duration_seconds(scan.status, scan.metadata_json),
    )


def list_scans(
    session: Session,
    *,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
    status: ScanStatus | None = None,
    agent_id: UUID | None = None,
    sort_by: ScanSortBy = "timestamp",
    sort_order: SortOrder = "desc",
) -> ScanListResponse:
    predicates = [ScanRecord.org_id == org_id]
    if status is not None:
        predicates.append(ScanRecord.status == status)
    if agent_id is not None:
        predicates.append(ScanRecord.agent_id == agent_id)

    total = session.exec(
        select(func.count()).select_from(ScanRecord).where(*predicates)
    ).one()

    column = _SCAN_SORT_COLUMNS[sort_by]
    direction = column.desc() if sort_order == "desc" else column.asc()
    rows = session.exec(
        select(ScanRecord, Agent.display_name)
        .outerjoin(Agent, Agent.id == ScanRecord.agent_id)
        .where(*predicates)
        .order_by(direction, ScanRecord.scan_id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    ids = [scan.scan_id for scan, _ in rows]
    host_counts: dict[UUID, int] = {}
    finding_agg: dict[UUID, tuple[int, int | None]] = {}
    if ids:
        host_counts = dict(
            session.exec(
                select(ScanHostRecord.scan_id, func.count())
                .where(ScanHostRecord.scan_id.in_(ids))
                .group_by(ScanHostRecord.scan_id)
            ).all()
        )
        finding_agg = {
            scan_id: (count, rank)
            for scan_id, count, rank in session.exec(
                select(
                    FindingRecord.scan_id,
                    func.count(),
                    func.max(_SEVERITY_RANK),
                )
                .where(FindingRecord.scan_id.in_(ids))
                .group_by(FindingRecord.scan_id)
            ).all()
        }

    return ScanListResponse(
        data=[
            _to_scan_summary(
                scan,
                host_count=host_counts.get(scan.scan_id, 0),
                finding_count=finding_agg.get(scan.scan_id, (0, None))[0],
                highest_severity=_severity_from_rank(
                    finding_agg.get(scan.scan_id, (0, None))[1]
                ),
                box_name=box_name,
            )
            for scan, box_name in rows
        ],
        total=total,
        page=page,
    )


def list_findings(
    session: Session,
    *,
    org_id: UUID,
    host_id: UUID | None = None,
    severity: Severity | None = None,
    scan_id: UUID | None = None,
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
    if severity is not None:
        base = base.where(FindingRecord.severity == severity)
    if scan_id is not None:
        base = base.where(FindingRecord.scan_id == scan_id)

    total = session.exec(
        select(func.count()).select_from(base.subquery())
    ).one()
    rows = session.exec(
        base.order_by(FindingRecord.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    return FindingListResponse(
        data=findings_with_risk(session, rows),
        total=total,
        page=page,
    )


def get_finding_detail(
    session: Session, finding_id: UUID, *, org_id: UUID
) -> FindingRead | None:
    row = session.exec(
        select(FindingRecord, ScanHostRecord.host_id)
        .join(ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id)
        .outerjoin(ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id)
        .where(
            FindingRecord.finding_id == finding_id,
            ScanRecord.org_id == org_id,
        )
    ).first()
    if row is None:
        return None
    return findings_with_risk(session, [row])[0]


def get_scan_risk_summary(
    session: Session, scan_id: UUID, *, org_id: UUID, top_limit: int = 10
) -> ScanRiskSummaryResponse | None:
    scan = session.exec(
        select(ScanRecord).where(
            ScanRecord.scan_id == scan_id,
            ScanRecord.org_id == org_id,
        )
    ).first()
    if scan is None:
        return None

    rows = session.exec(
        select(FindingRecord, ScanHostRecord.host_id)
        .outerjoin(ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id)
        .where(FindingRecord.scan_id == scan_id)
    ).all()
    ids = [finding.id for finding, _host_id in rows]
    snapshots = {
        snapshot.finding_id: snapshot
        for snapshot in session.exec(
            select(RiskSnapshotRecord).where(RiskSnapshotRecord.finding_id.in_(ids))
        ).all()
    } if ids else {}

    cve_ids = {
        finding.cve_id.upper()
        for finding, _host_id in rows
        if finding.cve_id is not None
    }
    kev_ids: set[str] = set()
    if cve_ids:
        kev_ids = set(
            session.exec(
                select(KevRecord.cve_id).where(KevRecord.cve_id.in_(cve_ids))
            ).all()
        )

    severity_counts = {label: 0 for label in SEVERITY_ORDER}
    for finding, _host_id in rows:
        severity_counts[finding.severity] += 1

    ranked = sorted(
        rows,
        key=lambda row: (
            snapshots[row[0].id].risk_score if row[0].id in snapshots else -1,
            SEVERITY_ORDER.get(row[0].severity, 0),
            -int(row[0].id or 0),
        ),
        reverse=True,
    )[:top_limit]
    scores = [snapshot.risk_score for snapshot in snapshots.values()]

    return ScanRiskSummaryResponse(
        scan_id=scan_id,
        total_findings=len(rows),
        scored_findings=len(scores),
        confirmed_findings=sum(
            finding.confidence == "confirmed" for finding, _host_id in rows
        ),
        kev_findings=sum(
            finding.cve_id is not None and finding.cve_id.upper() in kev_ids
            for finding, _host_id in rows
        ),
        average_risk_score=(round(sum(scores) / len(scores), 2) if scores else None),
        max_risk_score=max(scores) if scores else None,
        severity=SeverityBreakdown(**severity_counts),
        top_findings=[
            _to_finding_read(finding, host_id, snapshots.get(finding.id))
            for finding, host_id in ranked
        ],
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


def _severity_from_rank(rank: int | None) -> str | None:
    if not rank:
        return None
    return _SEVERITY_RANK_TO_LABEL.get(rank)


def _to_scan_summary(
    scan: ScanRecord,
    *,
    host_count: int,
    finding_count: int,
    highest_severity: str | None,
    box_name: str | None,
) -> ScanSummary:
    return ScanSummary(
        scan_id=scan.scan_id,
        timestamp=scan.timestamp,
        subnet=scan.subnet,
        scan_mode=scan.scan_mode,
        status=scan.status,
        host_count=host_count,
        finding_count=finding_count,
        highest_severity=highest_severity,
        agent_id=scan.agent_id,
        box_name=box_name,
        duration=scan_duration_seconds(scan.status, scan.metadata_json),
    )


def _to_host_summary(host: HostRecord) -> HostSummary:
    return HostSummary(
        host_id=host.id,
        ip=host.ip,
        mac=host.mac,
        hostname=host.hostname,
        vendor=host.vendor,
        operating_system=_to_operating_system(host.operating_system_json),
        first_seen_at=host.first_seen_at,
        last_seen_at=host.last_seen_at,
        open_ports_count=host.open_ports_count,
        highest_severity=host.highest_severity,
    )


def _to_operating_system(
    value: dict[str, object] | None,
) -> OperatingSystemDetection | None:
    if value is None:
        return None
    return OperatingSystemDetection.model_validate(value)


def _to_industrial_services(
    values: list[dict[str, object]],
) -> list[ModbusTcpServicePayload]:
    return [ModbusTcpServicePayload.model_validate(value) for value in values]


def findings_with_risk(session: Session, rows) -> list[FindingRead]:
    ids = [finding.id for finding, _host_id in rows]
    snapshots = {
        snapshot.finding_id: snapshot
        for snapshot in session.exec(
            select(RiskSnapshotRecord).where(RiskSnapshotRecord.finding_id.in_(ids))
        ).all()
    } if ids else {}
    return [
        _to_finding_read(finding, host_id, snapshots.get(finding.id))
        for finding, host_id in rows
    ]


def _to_finding_read(
    finding: FindingRecord,
    host_id: UUID | None,
    risk: RiskSnapshotRecord | None = None,
) -> FindingRead:
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
        risk_score=risk.risk_score if risk else None,
        exploitability=risk.exploitability if risk else None,
        confidence=risk.confidence if risk else None,
        risk_rationale=risk.rationale if risk else None,
    )
