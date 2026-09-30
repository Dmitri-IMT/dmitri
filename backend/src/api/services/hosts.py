from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from api.core.severity import SEVERITY_ORDER
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    utc_now,
)
from api.schemas.scan import ScanIngestRequest
from api.services.activity import ActivityAppend, append_activity


def identity_key(mac: str | None, ip: str) -> str:
    if mac:
        return f"mac:{mac.upper()}"
    return f"ip:{ip}"


def upsert_hosts_for_scan(
    session: Session, scan_record: ScanRecord, scan: ScanIngestRequest
) -> None:
    del scan
    scan_host_records = session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_record.scan_id)
    ).all()

    current_ips_by_mac: dict[str, set[str]] = defaultdict(set)
    for scan_host in scan_host_records:
        if scan_host.mac:
            current_ips_by_mac[scan_host.mac.upper()].add(scan_host.ip)
    ambiguous_macs = {
        mac: ips for mac, ips in current_ips_by_mac.items() if len(ips) > 1
    }
    for mac, ips in ambiguous_macs.items():
        _split_ambiguous_mac_hosts(
            session,
            scan_record=scan_record,
            mac=mac,
            ips=ips,
        )

    existing_hosts = session.exec(
        select(HostRecord).where(
            HostRecord.org_id.is_not_distinct_from(scan_record.org_id)
        )
    ).all()
    mac_host_counts: dict[str, int] = defaultdict(int)
    for host in existing_hosts:
        if host.mac:
            mac_host_counts[host.mac.upper()] += 1
    ambiguous_macs.update(
        {
            mac: set()
            for mac, count in mac_host_counts.items()
            if count > 1 and mac not in ambiguous_macs
        }
    )

    org_has_prior_completed = (
        session.exec(
            select(ScanRecord.scan_id)
            .where(
                ScanRecord.org_id == scan_record.org_id,
                ScanRecord.status == "completed",
                ScanRecord.scan_id != scan_record.scan_id,
                ScanRecord.timestamp < scan_record.timestamp,
            )
            .limit(1)
        ).first()
        is not None
    )

    for sh in scan_host_records:
        key = (
            f"ip:{sh.ip}"
            if sh.mac and sh.mac.upper() in ambiguous_macs
            else identity_key(sh.mac, sh.ip)
        )
        host = session.exec(
            select(HostRecord).where(
                HostRecord.org_id.is_not_distinct_from(scan_record.org_id),
                HostRecord.identity_key == key,
            )
        ).first()

        if host is None:
            host = HostRecord(
                org_id=scan_record.org_id,
                identity_key=key,
                ip=sh.ip,
                mac=sh.mac,
                hostname=sh.hostname,
                vendor=sh.vendor,
                operating_system_json=sh.operating_system_json,
                open_ports_count=open_ports_count(session, sh.id),
                highest_severity=highest_severity(session, sh.id),
                first_seen_at=scan_record.timestamp,
                last_seen_at=scan_record.timestamp,
            )
            session.add(host)
            session.flush()
            if org_has_prior_completed:
                append_activity(
                    session,
                    ActivityAppend(
                        org_id=scan_record.org_id,
                        kind="machine_first_seen",
                        occurred_at=utc_now(),
                        actor_user_id=None,
                        subject_id=host.id,
                        payload={"hostname": sh.hostname},
                    ),
                )
        else:
            host.first_seen_at = min(host.first_seen_at, scan_record.timestamp)
            if scan_record.timestamp >= host.last_seen_at:
                host.last_seen_at = scan_record.timestamp
                host.ip = sh.ip
                if sh.mac is not None:
                    host.mac = sh.mac
                host.hostname = sh.hostname
                if sh.vendor.strip().casefold() != "unknown":
                    host.vendor = sh.vendor
                if sh.operating_system_json is not None:
                    host.operating_system_json = sh.operating_system_json
                host.open_ports_count = open_ports_count(session, sh.id)
                host.highest_severity = highest_severity(session, sh.id)

        sh.host_id = host.id


def repair_ambiguous_mac_identities(session: Session) -> int:
    groups = find_ambiguous_mac_identities(session)
    for scan_record, mac, ips in groups:
        _split_ambiguous_mac_hosts(
            session,
            scan_record=scan_record,
            mac=mac,
            ips=ips,
        )
    return len(groups)


def find_ambiguous_mac_identities(
    session: Session,
) -> list[tuple[ScanRecord, str, set[str]]]:
    scans = session.exec(select(ScanRecord).order_by(ScanRecord.timestamp.asc())).all()
    groups: list[tuple[ScanRecord, str, set[str]]] = []
    for scan_record in scans:
        scan_hosts = session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_record.scan_id)
        ).all()
        rows_by_mac: dict[str, list[ScanHostRecord]] = defaultdict(list)
        for scan_host in scan_hosts:
            if scan_host.mac:
                rows_by_mac[scan_host.mac.upper()].append(scan_host)

        for mac, rows in rows_by_mac.items():
            ips = {row.ip for row in rows}
            host_ids = {row.host_id for row in rows}
            if len(ips) > 1 and len(host_ids) < len(ips):
                groups.append((scan_record, mac, ips))
    return groups


def _split_ambiguous_mac_hosts(
    session: Session,
    *,
    scan_record: ScanRecord,
    mac: str,
    ips: set[str],
) -> None:
    history = session.exec(
        select(ScanHostRecord, ScanRecord)
        .join(ScanRecord, ScanHostRecord.scan_id == ScanRecord.scan_id)
        .where(ScanRecord.org_id == scan_record.org_id)
        .where(func.upper(ScanHostRecord.mac) == mac)
        .where(ScanHostRecord.ip.in_(ips))
        .order_by(ScanRecord.timestamp.asc(), ScanRecord.scan_id.asc())
    ).all()
    rows_by_ip: dict[str, list[tuple[ScanHostRecord, ScanRecord]]] = defaultdict(list)
    for scan_host, scan in history:
        rows_by_ip[scan_host.ip].append((scan_host, scan))

    existing_hosts = session.exec(
        select(HostRecord).where(
            HostRecord.org_id == scan_record.org_id,
            func.upper(HostRecord.mac) == mac,
        )
    ).all()
    org_has_prior_completed = (
        session.exec(
            select(ScanRecord.scan_id)
            .where(
                ScanRecord.org_id == scan_record.org_id,
                ScanRecord.status == "completed",
                ScanRecord.scan_id != scan_record.scan_id,
                ScanRecord.timestamp < scan_record.timestamp,
            )
            .limit(1)
        ).first()
        is not None
    )
    used_host_ids = set()
    host_ids_by_ip: dict[str, UUID] = {}
    for ip in sorted(ips):
        identity = f"ip:{ip}"
        host = session.exec(
            select(HostRecord).where(
                HostRecord.org_id.is_not_distinct_from(scan_record.org_id),
                HostRecord.identity_key == identity,
            )
        ).first()
        if host is None:
            host = next(
                (item for item in existing_hosts if item.identity_key == identity),
                None,
            )
        if host is None:
            host = next(
                (
                    item
                    for item in existing_hosts
                    if item.id not in used_host_ids and item.ip == ip
                ),
                None,
            )
        if host is None:
            host = HostRecord(
                org_id=scan_record.org_id,
                identity_key=identity,
                ip=ip,
                mac=mac,
                hostname=ip,
                vendor="unknown",
                open_ports_count=0,
                first_seen_at=scan_record.timestamp,
                last_seen_at=scan_record.timestamp,
            )
            session.add(host)
            session.flush()
            existing_hosts.append(host)
            if org_has_prior_completed:
                append_activity(
                    session,
                    ActivityAppend(
                        org_id=scan_record.org_id,
                        kind="machine_first_seen",
                        occurred_at=utc_now(),
                        actor_user_id=None,
                        subject_id=host.id,
                        payload={"hostname": ip},
                    ),
                )
        host.identity_key = identity
        host.mac = mac
        used_host_ids.add(host.id)
        host_ids_by_ip[ip] = host.id

        observations = rows_by_ip[ip]
        if observations:
            latest_scan_host, latest_scan = observations[-1]
            host.ip = ip
            host.hostname = latest_scan_host.hostname
            host.vendor = latest_scan_host.vendor
            host.operating_system_json = latest_scan_host.operating_system_json
            host.first_seen_at = min(scan.timestamp for _, scan in observations)
            host.last_seen_at = latest_scan.timestamp
            session.add(host)
            for observed_scan_host, _ in observations:
                observed_scan_host.host_id = host.id
                session.add(observed_scan_host)

    from api.services.inventory import rebuild_host_inventory

    rebuild_host_inventory(session, list(host_ids_by_ip.values()))


def open_ports_count(session: Session, scan_host_id: int | None) -> int:
    ports = session.exec(
        select(PortRecord).where(PortRecord.scan_host_id == scan_host_id)
    ).all()
    return sum(1 for port in ports if port.state == "open")


def highest_severity(session: Session, scan_host_id: int | None) -> str | None:
    findings = session.exec(
        select(FindingRecord).where(FindingRecord.scan_host_id == scan_host_id)
    ).all()
    highest: str | None = None
    for finding in findings:
        if highest is None or (
            SEVERITY_ORDER[finding.severity] > SEVERITY_ORDER[highest]
        ):
            highest = finding.severity
    return highest
