from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

from sqlalchemy import Row, Select, and_, case, cast
from sqlalchemy.dialects.postgresql import INET
from sqlmodel import Session, func, select

from api.core.error_codes import scan_error_code
from api.core.scan_read import scan_duration_seconds
from api.core.severity import SEVERITY_ORDER, Severity
from api.models.command import Agent
from api.models.persistence import (
    FindingRecord,
    HostFindingRecord,
    HostPortRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
    utc_now,
)
from api.schemas.read import (
    FindingListResponse,
    FindingRead,
    HostDetailResponse,
    HostGroup,
    HostListResponse,
    HostPort,
    HostScanHistoryEntry,
    HostSortBy,
    HostSummary,
    Port,
    ScanDetailResponse,
    ScanHostView,
    ScanListResponse,
    ScanSortBy,
    ScanStatus,
    ScanSummary,
    SortOrder,
)
from api.services import commands
from api.services.hosts import highest_severity, open_ports_count

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
QUIET_AFTER_DAYS = 7

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
    "vulnerability_count": HostRecord.vulnerability_count,
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
    group: HostGroup = "active",
) -> HostListResponse:
    cutoff = utc_now() - timedelta(days=QUIET_AFTER_DAYS)
    quiet_pred = HostRecord.last_seen_at < cutoff
    group_pred = quiet_pred if group == "quiet" else HostRecord.last_seen_at >= cutoff
    total = session.exec(
        select(func.count())
        .select_from(HostRecord)
        .where(HostRecord.org_id == org_id, group_pred)
    ).one()
    quiet_total = session.exec(
        select(func.count())
        .select_from(HostRecord)
        .where(HostRecord.org_id == org_id, quiet_pred)
    ).one()
    column = _HOST_SORT_COLUMNS[sort_by]
    direction = column.desc() if sort_order == "desc" else column.asc()
    hosts = session.exec(
        select(HostRecord)
        .where(HostRecord.org_id == org_id, group_pred)
        .order_by(direction, HostRecord.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    return HostListResponse(
        data=[_to_host_summary(host) for host in hosts],
        total=total,
        quiet_total=quiet_total,
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

    ports = [
        HostPort(
            port=row.port,
            protocol=row.protocol,
            service=row.service,
            version=row.version,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
        )
        for row in session.exec(
            select(HostPortRecord)
            .where(HostPortRecord.host_id == host_id)
            .order_by(HostPortRecord.port.asc())
        ).all()
    ]

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
        machine_type=host.machine_type or "unknown",
        vulnerability_count=host.vulnerability_count,
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

    findings = to_finding_reads(
        session.exec(
            finding_read_query().where(FindingRecord.scan_id == scan_id)
        ).all()
    )

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
    base = finding_read_query().join(
        ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id
    ).where(ScanRecord.org_id == org_id)
    if host_id is not None:
        base = base.where(ScanHostRecord.host_id == host_id)
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
        data=to_finding_reads(rows),
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
        first_seen_at=host.first_seen_at,
        last_seen_at=host.last_seen_at,
        open_ports_count=host.open_ports_count,
        machine_type=host.machine_type or "unknown",
        vulnerability_count=host.vulnerability_count,
        highest_severity=host.highest_severity,
    )


def finding_read_query() -> Select:
    """Findings joined to their machine and its finding life.

    Callers add their own filters, sort and paging, then map the rows with
    `to_finding_reads`.
    """
    return (
        select(
            FindingRecord,
            ScanHostRecord.host_id,
            HostRecord.hostname,
            HostFindingRecord,
        )
        .outerjoin(
            ScanHostRecord, FindingRecord.scan_host_id == ScanHostRecord.id
        )
        .outerjoin(HostRecord, ScanHostRecord.host_id == HostRecord.id)
        .outerjoin(
            HostFindingRecord,
            and_(
                HostFindingRecord.host_id == HostRecord.id,
                HostFindingRecord.dedupe_key == FindingRecord.dedupe_key,
            ),
        )
    )


def to_finding_reads(rows: Sequence[Row]) -> list[FindingRead]:
    return [
        _to_finding_read(
            row.FindingRecord, row.host_id, row.hostname, row.HostFindingRecord
        )
        for row in rows
    ]


def _to_finding_read(
    finding: FindingRecord,
    host_id: UUID | None,
    hostname: str | None,
    life: HostFindingRecord | None,
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
        host_hostname=hostname,
        first_seen_at=life.first_seen_at if life else None,
        last_seen_at=life.last_seen_at if life else None,
        fixed_at=life.fixed_at if life else None,
    )
