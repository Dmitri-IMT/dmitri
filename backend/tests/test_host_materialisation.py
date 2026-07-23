from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from api.models.persistence import HostRecord, ScanHostRecord
from api.schemas.scan import Host, ScanResult
from api.services.persistence import persist_scan
from sqlmodel import Session, select


def _scan(scan_id, timestamp: datetime, hosts: list[Host]) -> ScanResult:
    return ScanResult(
        scan_id=scan_id,
        timestamp=timestamp,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=hosts,
    )


def _host(
    ip: str, mac: str | None, hostname: str = "host", vendor: str = "vendor"
) -> Host:
    return Host(ip=ip, mac=mac, hostname=hostname, vendor=vendor, ports=[])


def test_same_mac_across_scans_materialises_single_host(
    runtime_session: Session,
) -> None:
    mac = "AA:BB:CC:DD:EE:FF"
    timestamp_a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamp_b = datetime(2026, 6, 1, tzinfo=timezone.utc)

    scan_a = _scan(
        uuid4(),
        timestamp_a,
        [_host("192.168.1.10", mac, hostname="old-name", vendor="old-vendor")],
    )
    scan_b = _scan(
        uuid4(),
        timestamp_b,
        [_host("192.168.1.11", mac, hostname="new-name", vendor="new-vendor")],
    )

    persist_scan(runtime_session, scan_a)
    persist_scan(runtime_session, scan_b)

    hosts = runtime_session.exec(select(HostRecord)).all()
    assert len(hosts) == 1
    host = hosts[0]
    assert host.first_seen_at == timestamp_a
    assert host.last_seen_at == timestamp_b
    assert host.ip == "192.168.1.11"
    assert host.hostname == "new-name"
    assert host.vendor == "new-vendor"

    scan_hosts = runtime_session.exec(select(ScanHostRecord)).all()
    assert len(scan_hosts) == 2
    assert all(sh.host_id == host.id for sh in scan_hosts)


def test_mac_absent_scan_host_resolves_by_ip(runtime_session: Session) -> None:
    timestamp_a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamp_b = datetime(2026, 2, 1, tzinfo=timezone.utc)

    scan_a = _scan(uuid4(), timestamp_a, [_host("192.168.1.20", None)])
    scan_b = _scan(uuid4(), timestamp_b, [_host("192.168.1.20", None)])

    persist_scan(runtime_session, scan_a)
    persist_scan(runtime_session, scan_b)

    hosts = runtime_session.exec(select(HostRecord)).all()
    assert len(hosts) == 1
    assert hosts[0].first_seen_at == timestamp_a
    assert hosts[0].last_seen_at == timestamp_b


def test_host_only_in_latest_scan_has_first_seen_equal_latest(
    runtime_session: Session,
) -> None:
    timestamp_a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamp_b = datetime(2026, 2, 1, tzinfo=timezone.utc)

    scan_a = _scan(uuid4(), timestamp_a, [_host("192.168.1.30", "11:22:33:44:55:66")])
    scan_b = _scan(uuid4(), timestamp_b, [_host("192.168.1.31", "77:88:99:AA:BB:CC")])

    persist_scan(runtime_session, scan_a)
    persist_scan(runtime_session, scan_b)

    hosts = runtime_session.exec(select(HostRecord)).all()
    new_host = next(h for h in hosts if h.mac == "77:88:99:AA:BB:CC")
    assert new_host.first_seen_at == timestamp_b
    assert new_host.last_seen_at == timestamp_b


def test_every_scan_host_gets_host_id_assigned(runtime_session: Session) -> None:
    scan = _scan(
        uuid4(),
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        [
            _host("192.168.1.40", "01:02:03:04:05:06"),
            _host("192.168.1.41", None),
        ],
    )

    persist_scan(runtime_session, scan)

    scan_hosts = runtime_session.exec(select(ScanHostRecord)).all()
    assert len(scan_hosts) == 2
    assert all(sh.host_id is not None for sh in scan_hosts)
