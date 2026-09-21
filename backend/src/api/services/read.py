from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import timedelta
from ipaddress import ip_address
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Row, Select, and_, case, cast
from sqlalchemy.dialects.postgresql import INET
from sqlmodel import Session, func, select

from api.core.error_codes import scan_error_code
from api.core.scan_read import scan_duration_seconds
from api.core.severity import SEVERITY_ORDER, Severity
from api.models.command import Agent
from api.models.persistence import (
    ExposureRecord,
    FindingRecord,
    HostFindingRecord,
    HostPortRecord,
    HostRecord,
    IndustrialServiceRecord,
    KevRecord,
    ModbusUnitRecord,
    PortRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
    utc_now,
)
from api.schemas.operating_system import OperatingSystemDetection
from api.schemas.read import (
    ExposureRead,
    FindingListResponse,
    FindingModbusUnitRef,
    FindingRead,
    HostDetailResponse,
    HostGroup,
    HostListResponse,
    HostPort,
    HostScanHistoryEntry,
    HostSortBy,
    HostSummary,
    IndustrialServiceView,
    ModbusAddressRangeView,
    ModbusDeviceIdentificationView,
    ModbusUnitView,
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
from api.schemas.scan import DeviceProfilePayload
from api.services import commands
from api.services.hosts import highest_severity, open_ports_count
from api.services.industrial import industrial_services_for_scan_host
from api.services.inventory import latest_scan_host_for_host

logger = logging.getLogger(__name__)

_ADDRESS_RANGES = TypeAdapter(list[ModbusAddressRangeView])

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

    summary = _to_host_summary(host)
    unreadable = list(summary.unreadable_fields)
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
    latest_pair = latest_scan_host_for_host(session, host_id, org_id=org_id)
    latest_scan_host = latest_pair[0] if latest_pair else None
    latest_scan = latest_pair[1] if latest_pair else None
    industrial_services = (
        _industrial_service_views(session, latest_scan_host.id, unreadable)
        if latest_scan_host
        else []
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
            operating_system=_validate_or_degrade(
                OperatingSystemDetection,
                scan_host.operating_system_json,
                field="operating_system",
                unreadable=unreadable,
                context=f"scan_host_id={scan_host.id}",
            ),
            open_ports_count=open_ports_count(session, scan_host.id),
            highest_severity=highest_severity(session, scan_host.id),
        )
        for scan_host, scan in scan_history_rows
    ]

    payload = summary.model_dump()
    payload["unreadable_fields"] = unreadable
    assessment_available = (
        latest_scan is not None
        and latest_scan.assessment_policy_version is not None
    )
    if assessment_available and latest_scan_host is not None:
        payload["machine_type"] = latest_scan_host.machine_type or "unknown"
        payload["device_profile"] = _device_profile(
            latest_scan_host.device_profile_json
        )
    return HostDetailResponse(
        **payload,
        assessment_status=(
            "available" if assessment_available else "unavailable"
        ),
        assessment_policy_version=(
            latest_scan.assessment_policy_version
            if assessment_available
            else None
        ),
        exposures=(
            _exposure_reads(
                session,
                scan_id=latest_scan.scan_id,
                scan_host_id=latest_scan_host.id,
            )
            if assessment_available and latest_scan_host is not None
            else []
        ),
        ports=ports,
        industrial_services=industrial_services,
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
    assessment_available = scan.assessment_policy_version is not None
    hosts = [
        _to_scan_host_view(
            session, scan_host, assessment_available=assessment_available
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
        assessment_status=(
            "available" if assessment_available else "unavailable"
        ),
        assessment_policy_version=scan.assessment_policy_version,
        exposures=(
            _exposure_reads(session, scan_id=scan.scan_id)
            if assessment_available
            else []
        ),
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


def get_finding_detail(
    session: Session, finding_id: UUID, *, org_id: UUID
) -> FindingRead | None:
    row = session.exec(
        finding_read_query()
        .join(ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id)
        .where(
            FindingRecord.finding_id == finding_id,
            ScanRecord.org_id == org_id,
        )
    ).first()
    if row is None:
        return None
    return to_finding_reads([row])[0]


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
        finding_read_query().where(FindingRecord.scan_id == scan_id)
    ).all()

    cve_ids = {
        row.FindingRecord.cve_id.upper()
        for row in rows
        if row.FindingRecord.cve_id is not None
    }
    kev_ids: set[str] = set()
    if cve_ids:
        kev_ids = set(
            session.exec(
                select(KevRecord.cve_id).where(KevRecord.cve_id.in_(cve_ids))
            ).all()
        )

    severity_counts = {label: 0 for label in SEVERITY_ORDER}
    for row in rows:
        severity_counts[row.FindingRecord.severity] += 1

    ranked = sorted(
        rows,
        key=lambda row: (
            row.RiskSnapshotRecord.risk_score if row.RiskSnapshotRecord else -1,
            SEVERITY_ORDER.get(row.FindingRecord.severity, 0),
            -int(row.FindingRecord.id or 0),
        ),
        reverse=True,
    )[:top_limit]
    scores = [
        row.RiskSnapshotRecord.risk_score for row in rows if row.RiskSnapshotRecord
    ]

    return ScanRiskSummaryResponse(
        scan_id=scan_id,
        total_findings=len(rows),
        scored_findings=len(scores),
        confirmed_findings=sum(
            row.FindingRecord.confidence == "confirmed" for row in rows
        ),
        kev_findings=sum(
            row.FindingRecord.cve_id is not None
            and row.FindingRecord.cve_id.upper() in kev_ids
            for row in rows
        ),
        average_risk_score=(round(sum(scores) / len(scores), 2) if scores else None),
        max_risk_score=max(scores) if scores else None,
        severity=SeverityBreakdown(**severity_counts),
        top_findings=to_finding_reads(ranked),
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
    unreadable: list[str] = []
    return HostSummary(
        host_id=host.id,
        ip=host.ip,
        mac=host.mac,
        hostname=host.hostname,
        vendor=host.vendor,
        operating_system=_validate_or_degrade(
            OperatingSystemDetection,
            host.operating_system_json,
            field="operating_system",
            unreadable=unreadable,
            context=f"host_id={host.id}",
        ),
        first_seen_at=host.first_seen_at,
        last_seen_at=host.last_seen_at,
        open_ports_count=host.open_ports_count,
        machine_type=host.machine_type or "unknown",
        device_profile=_device_profile(host.device_profile_json),
        vulnerability_count=host.vulnerability_count,
        highest_severity=host.highest_severity,
        unreadable_fields=unreadable,
    )


def _to_scan_host_view(
    session: Session,
    scan_host: ScanHostRecord,
    *,
    assessment_available: bool,
) -> ScanHostView:
    unreadable: list[str] = []
    return ScanHostView(
        host_id=scan_host.host_id,
        ip=scan_host.ip,
        mac=scan_host.mac,
        hostname=scan_host.hostname,
        vendor=scan_host.vendor,
        operating_system=_validate_or_degrade(
            OperatingSystemDetection,
            scan_host.operating_system_json,
            field="operating_system",
            unreadable=unreadable,
            context=f"scan_host_id={scan_host.id}",
        ),
        ports=_ports_for_scan_host(session, scan_host.id),
        machine_type=(scan_host.machine_type if assessment_available else None),
        device_profile=(
            _device_profile(scan_host.device_profile_json)
            if assessment_available
            else None
        ),
        industrial_services=_industrial_service_views(
            session, scan_host.id, unreadable
        ),
        unreadable_fields=unreadable,
    )


def _device_profile(value: dict | None) -> DeviceProfilePayload | None:
    if value is None:
        return None
    return DeviceProfilePayload.model_validate(value)


def _exposure_reads(
    session: Session,
    *,
    scan_id: UUID,
    scan_host_id: int | None = None,
) -> list[ExposureRead]:
    predicate = [ExposureRecord.scan_id == scan_id]
    if scan_host_id is not None:
        predicate.append(ExposureRecord.scan_host_id == scan_host_id)
    exposures = session.exec(select(ExposureRecord).where(*predicate)).all()
    if not exposures:
        return []

    port_ids = {row.port_id for row in exposures}
    scan_host_ids = {row.scan_host_id for row in exposures}
    host_ids = dict(
        session.exec(
            select(ScanHostRecord.id, ScanHostRecord.host_id).where(
                ScanHostRecord.id.in_(scan_host_ids)
            )
        ).all()
    )
    related: dict[int, list[UUID]] = {}
    for port_id, finding_id in session.exec(
        select(FindingRecord.port_id, FindingRecord.finding_id).where(
            FindingRecord.scan_id == scan_id,
            FindingRecord.port_id.in_(port_ids),
        )
    ).all():
        if port_id is not None:
            related.setdefault(port_id, []).append(finding_id)

    exposures.sort(
        key=lambda row: (ip_address(row.ip), row.protocol, row.port)
    )
    result = []
    for row in exposures:
        host_id = host_ids.get(row.scan_host_id)
        if host_id is None:
            raise ValueError("exposure scan host has no inventory host")
        result.append(
            ExposureRead(
                exposure_id=row.exposure_id,
                scan_id=row.scan_id,
                host_id=host_id,
                ip=row.ip,
                port=row.port,
                protocol=row.protocol,
                observed_service=row.observed_service,
                observed_version=row.observed_version,
                role=row.role,
                attention=row.attention,
                confidence=row.confidence,
                reason=row.reason,
                evidence=row.evidence_json,
                related_finding_ids=sorted(
                    related.get(row.port_id, []), key=str
                ),
                detected_at=row.created_at,
            )
        )
    return result


def _validate_or_degrade(
    model, value, *, field: str, unreadable: list[str], context: str
):
    if value is None:
        return None
    try:
        if isinstance(model, TypeAdapter):
            return model.validate_python(value)
        return model.model_validate(value)
    except ValidationError:
        logger.warning("unreadable %s in %s", field, context)
        if field not in unreadable:
            unreadable.append(field)
        return None


def _industrial_service_views(
    session: Session, scan_host_id: int, unreadable: list[str]
) -> list[IndustrialServiceView]:
    services = industrial_services_for_scan_host(session, scan_host_id)
    if not services:
        return []
    service_ids = [service.id for service in services if service.id is not None]
    units_by_service: dict[int, list[ModbusUnitRecord]] = {}
    if service_ids:
        for unit in session.exec(
            select(ModbusUnitRecord)
            .where(ModbusUnitRecord.industrial_service_id.in_(service_ids))
            .order_by(ModbusUnitRecord.unit_id)
        ).all():
            units_by_service.setdefault(unit.industrial_service_id, []).append(unit)
    return [
        IndustrialServiceView(
            protocol=service.protocol,
            port=service.port,
            confidence=service.confidence,
            mapping_source=service.mapping_source,
            evidence_sources=list(service.evidence_sources_json),
            units=[
                _to_modbus_unit_view(unit, unreadable)
                for unit in units_by_service.get(service.id or -1, [])
            ],
        )
        for service in services
    ]


def _to_modbus_unit_view(
    unit: ModbusUnitRecord, unreadable: list[str]
) -> ModbusUnitView:
    context = f"modbus_unit_id={unit.id}"
    identification = _validate_or_degrade(
        ModbusDeviceIdentificationView,
        unit.identification_json,
        field="identification",
        unreadable=unreadable,
        context=context,
    )
    address_ranges = _validate_or_degrade(
        _ADDRESS_RANGES,
        unit.address_ranges_json,
        field="address_ranges",
        unreadable=unreadable,
        context=context,
    )
    return ModbusUnitView(
        id=unit.id,
        unit_id=unit.unit_id,
        status=unit.status,
        exception_code=unit.exception_code,
        error=unit.error,
        identification=identification,
        identification_sources=list(unit.identification_sources_json),
        address_ranges=address_ranges or [],
    )


def finding_read_query() -> Select:
    """Findings joined to their machine, finding life, and Modbus unit.

    Callers add their own filters, sort and paging, then map the rows with
    `to_finding_reads`.
    """
    return (
        select(
            FindingRecord,
            ScanHostRecord.host_id,
            HostRecord.hostname,
            HostFindingRecord,
            ModbusUnitRecord,
            IndustrialServiceRecord,
            RiskSnapshotRecord,
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
        .outerjoin(
            ModbusUnitRecord,
            FindingRecord.modbus_unit_id == ModbusUnitRecord.id,
        )
        .outerjoin(
            IndustrialServiceRecord,
            ModbusUnitRecord.industrial_service_id == IndustrialServiceRecord.id,
        )
        .outerjoin(
            RiskSnapshotRecord, RiskSnapshotRecord.finding_id == FindingRecord.id
        )
    )


def to_finding_reads(rows: Sequence[Row]) -> list[FindingRead]:
    return [
        _to_finding_read(
            row.FindingRecord,
            row.host_id,
            row.hostname,
            row.HostFindingRecord,
            row.ModbusUnitRecord,
            row.IndustrialServiceRecord,
            row.RiskSnapshotRecord,
        )
        for row in rows
    ]


def _finding_modbus_unit_ref(
    unit: ModbusUnitRecord | None,
    service: IndustrialServiceRecord | None,
) -> FindingModbusUnitRef | None:
    if unit is None or service is None or unit.id is None:
        return None
    return FindingModbusUnitRef(
        id=unit.id,
        unit_id=unit.unit_id,
        port=service.port,
    )


def _to_finding_read(
    finding: FindingRecord,
    host_id: UUID | None,
    hostname: str | None,
    life: HostFindingRecord | None,
    unit: ModbusUnitRecord | None,
    service: IndustrialServiceRecord | None,
    risk: RiskSnapshotRecord | None,
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
        modbus_unit=_finding_modbus_unit_ref(unit, service),
        detected_at=finding.created_at,
        risk_score=risk.risk_score if risk else None,
        exploitability=risk.exploitability if risk else None,
        confidence=risk.confidence if risk else None,
        risk_rationale=risk.rationale if risk else None,
        host_hostname=hostname,
        first_seen_at=life.first_seen_at if life else None,
        last_seen_at=life.last_seen_at if life else None,
        fixed_at=life.fixed_at if life else None,
    )

