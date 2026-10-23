from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, delete, or_, update
from sqlmodel import Session, select

from api.models.activity import ActivityKind
from api.models.command import Command
from api.models.identity import User
from api.models.persistence import (
    AIChatMessageRecord,
    AIExplanationRecord,
    AIScanAnalysisRecord,
    AIUsageRecord,
    CPERecord,
    DeletedScanRecord,
    EnrichmentJobRecord,
    ExposureRecord,
    FindingRecord,
    HostFindingRecord,
    HostPortRecord,
    HostRecord,
    IndustrialServiceRecord,
    ModbusUnitRecord,
    PortRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
    utc_now,
)
from api.services.activity import ActivityAppend, append_activity
from api.services.command_lifecycle import UNFINISHED_SCAN
from api.services.inventory import rebuild_host_inventory


class ScanRunningError(Exception):
    pass


@dataclass(frozen=True)
class ScanDeletion:
    deleted: int
    skipped: int
    machines_removed: int


def delete_scan(
    session: Session, *, scan_id: UUID, org_id: UUID, actor: User
) -> bool:
    scan = session.exec(
        select(ScanRecord)
        .where(ScanRecord.scan_id == scan_id, ScanRecord.org_id == org_id)
        .with_for_update()
    ).first()
    if scan is None:
        return False
    if scan.status in UNFINISHED_SCAN:
        raise ScanRunningError
    subnet = scan.subnet
    machines_removed = _delete_scans(session, [scan_id], org_id=org_id)
    _record(
        session,
        org_id=org_id,
        actor=actor,
        kind="scans_deleted",
        subject_id=scan_id,
        payload={
            "subnet": subnet,
            "count": "1",
            "machines_removed": str(machines_removed),
        },
    )
    session.commit()
    return True


def delete_all_scans(session: Session, *, org_id: UUID, actor: User) -> ScanDeletion:
    rows = session.exec(
        select(ScanRecord.scan_id, ScanRecord.status)
        .where(ScanRecord.org_id == org_id)
        .with_for_update()
    ).all()
    scan_ids = [scan_id for scan_id, status in rows if status not in UNFINISHED_SCAN]
    machines_removed = _delete_scans(session, scan_ids, org_id=org_id)
    result = ScanDeletion(
        deleted=len(scan_ids),
        skipped=len(rows) - len(scan_ids),
        machines_removed=machines_removed,
    )
    _record(
        session,
        org_id=org_id,
        actor=actor,
        kind="scans_deleted",
        subject_id=None,
        payload={
            "count": str(result.deleted),
            "skipped": str(result.skipped),
            "machines_removed": str(result.machines_removed),
        },
    )
    session.commit()
    return result


def delete_host(
    session: Session, *, host_id: UUID, org_id: UUID, actor: User
) -> bool:
    host = session.exec(
        select(HostRecord).where(HostRecord.id == host_id, HostRecord.org_id == org_id)
    ).first()
    if host is None:
        return False
    machine = host.hostname or host.ip
    _delete_hosts(session, [host_id])
    _record(
        session,
        org_id=org_id,
        actor=actor,
        kind="machines_deleted",
        subject_id=host_id,
        payload={"machine": machine, "count": "1"},
    )
    session.commit()
    return True


def delete_all_hosts(session: Session, *, org_id: UUID, actor: User) -> int:
    host_ids = list(
        session.exec(select(HostRecord.id).where(HostRecord.org_id == org_id)).all()
    )
    _delete_hosts(session, host_ids)
    _record(
        session,
        org_id=org_id,
        actor=actor,
        kind="machines_deleted",
        subject_id=None,
        payload={"count": str(len(host_ids))},
    )
    session.commit()
    return len(host_ids)


def _record(
    session: Session,
    *,
    org_id: UUID,
    actor: User,
    kind: ActivityKind,
    subject_id: UUID | None,
    payload: dict[str, str],
) -> None:
    append_activity(
        session,
        ActivityAppend(
            org_id=org_id,
            kind=kind,
            occurred_at=utc_now(),
            actor_user_id=actor.id,
            subject_id=subject_id,
            payload={"actor_email": actor.email, **payload},
        ),
    )


def _delete_scans(session: Session, scan_ids: list[UUID], *, org_id: UUID) -> int:
    if not scan_ids:
        return 0
    scan_host_ids = list(
        session.exec(
            select(ScanHostRecord.id).where(ScanHostRecord.scan_id.in_(scan_ids))
        ).all()
    )
    host_ids = set(
        session.exec(
            select(ScanHostRecord.host_id)
            .where(
                ScanHostRecord.scan_id.in_(scan_ids),
                ScanHostRecord.host_id.is_not(None),
            )
            .distinct()
        ).all()
    )
    _delete_evidence(session, scan_host_ids=scan_host_ids, scan_ids=scan_ids)
    session.execute(
        delete(AIChatMessageRecord).where(AIChatMessageRecord.scan_id.in_(scan_ids))
    )
    session.execute(
        delete(AIExplanationRecord).where(AIExplanationRecord.scan_id.in_(scan_ids))
    )
    session.execute(
        delete(AIScanAnalysisRecord).where(AIScanAnalysisRecord.scan_id.in_(scan_ids))
    )
    session.execute(
        update(AIUsageRecord)
        .where(AIUsageRecord.scan_id.in_(scan_ids))
        .values(scan_id=None)
    )
    session.execute(delete(Command).where(Command.scan_id.in_(scan_ids)))
    session.execute(delete(ScanRecord).where(ScanRecord.scan_id.in_(scan_ids)))
    session.add_all(
        DeletedScanRecord(scan_id=scan_id, org_id=org_id) for scan_id in scan_ids
    )
    session.flush()
    return _settle_hosts(session, host_ids)


def _delete_hosts(session: Session, host_ids: Collection[UUID]) -> None:
    if not host_ids:
        return
    scan_host_ids = list(
        session.exec(
            select(ScanHostRecord.id).where(ScanHostRecord.host_id.in_(host_ids))
        ).all()
    )
    finding_ids = _delete_evidence(session, scan_host_ids=scan_host_ids, scan_ids=[])
    session.execute(
        delete(AIChatMessageRecord).where(
            or_(
                and_(
                    AIChatMessageRecord.scope_type == "host",
                    AIChatMessageRecord.scope_id.in_(host_ids),
                ),
                and_(
                    AIChatMessageRecord.scope_type == "finding",
                    AIChatMessageRecord.scope_id.in_(finding_ids),
                ),
            )
        )
    )
    session.execute(
        delete(AIExplanationRecord).where(
            AIExplanationRecord.scope == "host",
            AIExplanationRecord.context_id.in_(host_ids),
        )
    )
    session.execute(delete(HostPortRecord).where(HostPortRecord.host_id.in_(host_ids)))
    session.execute(
        delete(HostFindingRecord).where(HostFindingRecord.host_id.in_(host_ids))
    )
    session.execute(delete(HostRecord).where(HostRecord.id.in_(host_ids)))


def _delete_evidence(
    session: Session, *, scan_host_ids: list[int], scan_ids: list[UUID]
) -> list[UUID]:
    port_ids = select(PortRecord.id).where(PortRecord.scan_host_id.in_(scan_host_ids))
    industrial_ids = select(IndustrialServiceRecord.id).where(
        IndustrialServiceRecord.scan_host_id.in_(scan_host_ids)
    )
    unit_ids = select(ModbusUnitRecord.id).where(
        ModbusUnitRecord.industrial_service_id.in_(industrial_ids)
    )
    findings = session.exec(
        select(FindingRecord.id, FindingRecord.finding_id).where(
            or_(
                FindingRecord.scan_id.in_(scan_ids),
                FindingRecord.scan_host_id.in_(scan_host_ids),
                FindingRecord.port_id.in_(port_ids),
                FindingRecord.modbus_unit_id.in_(unit_ids),
            )
        )
    ).all()
    finding_ids = [row_id for row_id, _ in findings]

    session.execute(
        delete(RiskSnapshotRecord).where(RiskSnapshotRecord.finding_id.in_(finding_ids))
    )
    session.execute(
        delete(EnrichmentJobRecord).where(
            or_(
                EnrichmentJobRecord.scan_id.in_(scan_ids),
                EnrichmentJobRecord.finding_id.in_(finding_ids),
                EnrichmentJobRecord.port_id.in_(port_ids),
            )
        )
    )
    session.execute(delete(FindingRecord).where(FindingRecord.id.in_(finding_ids)))
    session.execute(
        delete(ExposureRecord).where(
            or_(
                ExposureRecord.scan_id.in_(scan_ids),
                ExposureRecord.scan_host_id.in_(scan_host_ids),
            )
        )
    )
    session.execute(
        delete(ModbusUnitRecord).where(
            ModbusUnitRecord.industrial_service_id.in_(industrial_ids)
        )
    )
    session.execute(
        delete(IndustrialServiceRecord).where(
            IndustrialServiceRecord.scan_host_id.in_(scan_host_ids)
        )
    )
    session.execute(delete(ServiceRecord).where(ServiceRecord.port_id.in_(port_ids)))
    session.execute(delete(CPERecord).where(CPERecord.port_id.in_(port_ids)))
    session.execute(
        delete(PortRecord).where(PortRecord.scan_host_id.in_(scan_host_ids))
    )
    session.execute(delete(ScanHostRecord).where(ScanHostRecord.id.in_(scan_host_ids)))
    return [finding_id for _, finding_id in findings]


def _settle_hosts(session: Session, host_ids: set[UUID]) -> int:
    if not host_ids:
        return 0
    observed = set(
        session.exec(
            select(ScanHostRecord.host_id)
            .where(ScanHostRecord.host_id.in_(host_ids))
            .distinct()
        ).all()
    )
    orphans = host_ids - observed
    _delete_hosts(session, orphans)
    rebuild_host_inventory(session, list(observed))
    session.flush()
    return len(orphans)
