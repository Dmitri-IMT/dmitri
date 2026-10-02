from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from api.models.persistence import HostRecord, ScanHostRecord, ScanRecord
from api.services.hosts import (
    apply_observation,
    identity_key,
    retarget_split_mac_hosts,
)
from api.services.inventory import rebuild_host_inventory


def find_ambiguous_mac_identities(
    session: Session,
) -> list[tuple[ScanRecord, str, list[str]]]:
    mac = func.upper(ScanHostRecord.mac)
    ip_count = func.count(ScanHostRecord.ip)
    rows = session.exec(
        select(ScanRecord, mac, func.array_agg(ScanHostRecord.ip))
        .join(ScanHostRecord, ScanHostRecord.scan_id == ScanRecord.scan_id)
        .where(ScanHostRecord.mac.is_not(None))
        .group_by(ScanRecord.scan_id, mac)
        .having(ip_count > 1)
        .having(func.count(func.distinct(ScanHostRecord.host_id)) < ip_count)
        .order_by(ScanRecord.timestamp.asc(), ScanRecord.scan_id.asc())
    ).all()
    return [(scan, scan_mac, sorted(ips)) for scan, scan_mac, ips in rows]


def repair_ambiguous_mac_identities(session: Session) -> int:
    groups = find_ambiguous_mac_identities(session)
    host_ids: set[UUID] = set()
    for scan, mac, ips in groups:
        host_ids.update(_split_mac_history(session, scan.org_id, mac, ips))
    rebuild_host_inventory(session, list(host_ids))
    return len(groups)


def _split_mac_history(
    session: Session, org_id: UUID | None, mac: str, ips: list[str]
) -> set[UUID]:
    retarget_split_mac_hosts(session, org_id, {mac})
    history = session.exec(
        select(ScanHostRecord, ScanRecord)
        .join(ScanRecord, ScanHostRecord.scan_id == ScanRecord.scan_id)
        .where(
            ScanRecord.org_id.is_not_distinct_from(org_id),
            func.upper(ScanHostRecord.mac) == mac,
            ScanHostRecord.ip.in_(ips),
        )
        .order_by(ScanRecord.timestamp.asc(), ScanRecord.scan_id.asc())
    ).all()
    hosts: dict[str, HostRecord] = {}
    for scan_host, scan in history:
        host = hosts.get(scan_host.ip)
        if host is None:
            host = session.exec(
                select(HostRecord).where(
                    HostRecord.org_id.is_not_distinct_from(org_id),
                    HostRecord.identity_key == identity_key(None, scan_host.ip),
                )
            ).first()
        if host is None:
            host = HostRecord(
                org_id=org_id,
                identity_key=identity_key(None, scan_host.ip),
                ip=scan_host.ip,
                mac=scan_host.mac,
                hostname=scan_host.hostname,
                vendor=scan_host.vendor,
                operating_system_json=scan_host.operating_system_json,
                open_ports_count=0,
                first_seen_at=scan.timestamp,
                last_seen_at=scan.timestamp,
            )
            session.add(host)
            session.flush()
        else:
            apply_observation(session, host, scan_host, scan.timestamp)
        hosts[scan_host.ip] = host
        scan_host.host_id = host.id
        session.add(scan_host)
    return {host.id for host in hosts.values()}
