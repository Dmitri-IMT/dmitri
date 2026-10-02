from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import HostFindingRecord, HostRecord, ScanHostRecord
from api.schemas.scan import FindingPayload, HostPayload, ScanIngestRequest
from api.services.host_repair import repair_ambiguous_mac_identities
from api.services.persistence import persist_scan
from sqlmodel import Session, select


def _scan(
    scan_id,
    timestamp: datetime,
    hosts: list[HostPayload],
    findings: list[FindingPayload] | None = None,
) -> ScanIngestRequest:
    return ScanIngestRequest(
        scan_id=scan_id,
        timestamp=timestamp,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=hosts,
        findings=findings or [],
    )


def _host(
    ip: str,
    mac: str | None,
    hostname: str = "host",
    vendor: str = "vendor",
    operating_system: dict[str, object] | None = None,
) -> HostPayload:
    return HostPayload(
        ip=ip,
        mac=mac,
        hostname=hostname,
        vendor=vendor,
        operating_system=operating_system,
        ports=[],
    )


def _os(name: str, accuracy: int) -> dict[str, object]:
    return {
        "name": name,
        "accuracy": accuracy,
        "vendor": "Linux",
        "cpes": ["cpe:/o:linux:linux_kernel:5"],
    }


def _persist(session: Session, scan: ScanIngestRequest, org: Org, agent: Agent) -> None:
    persist_scan(
        session,
        scan,
        org_id=org.id,
        agent_id=agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )


def test_same_mac_across_scans_materialises_single_host(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
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

    _persist(runtime_session, scan_a, seeded_org, provisioned_agent)
    _persist(runtime_session, scan_b, seeded_org, provisioned_agent)

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


def test_same_mac_on_two_ips_in_one_scan_splits_hosts(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    mac = "36:D5:B4:1F:F5:E8"
    prior_scan = _scan(
        uuid4(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        [_host("172.20.10.8", mac, operating_system=_os("Windows 11", 91))],
    )
    _persist(runtime_session, prior_scan, seeded_org, provisioned_agent)

    scan_id = uuid4()
    scan = _scan(
        scan_id,
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        [
            _host("172.20.10.2", mac, operating_system=_os("Linux 2.6", 100)),
            _host("172.20.10.8", mac, operating_system=_os("Windows 11", 91)),
        ],
        findings=[
            FindingPayload(
                ip="172.20.10.2",
                severity="critical",
                title="VM vulnerability",
                description="VM issue",
                recommendation="Patch the VM",
                evidence="VM evidence",
            )
        ],
    )
    _persist(runtime_session, scan, seeded_org, provisioned_agent)

    hosts = runtime_session.exec(
        select(HostRecord).where(HostRecord.org_id == seeded_org.id)
    ).all()
    by_ip = {host.ip: host for host in hosts}
    assert set(by_ip) == {"172.20.10.2", "172.20.10.8"}
    assert by_ip["172.20.10.2"].id != by_ip["172.20.10.8"].id
    assert by_ip["172.20.10.2"].operating_system_json["name"] == "Linux 2.6"
    assert by_ip["172.20.10.8"].operating_system_json["name"] == "Windows 11"
    assert by_ip["172.20.10.2"].vulnerability_count == 1
    assert by_ip["172.20.10.8"].vulnerability_count == 0
    host_finding = runtime_session.exec(
        select(HostFindingRecord).where(
            HostFindingRecord.host_id == by_ip["172.20.10.2"].id
        )
    ).one()
    assert host_finding.fixed_at is None

    scan_hosts = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
    ).all()
    assert {item.ip: item.host_id for item in scan_hosts} == {
        "172.20.10.2": by_ip["172.20.10.2"].id,
        "172.20.10.8": by_ip["172.20.10.8"].id,
    }
    historical_scan_host = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == prior_scan.scan_id)
    ).one()
    assert historical_scan_host.host_id == by_ip["172.20.10.8"].id


def test_repair_ambiguous_mac_identities_splits_existing_history(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    mac = "36:D5:B4:1F:F5:E8"
    scan_id = uuid4()
    scan = _scan(
        scan_id,
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        [
            _host("172.20.10.2", mac, operating_system=_os("Linux", 100)),
            _host("172.20.10.8", mac, operating_system=_os("Windows 11", 91)),
        ],
    )
    _persist(runtime_session, scan, seeded_org, provisioned_agent)

    scan_hosts = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
    ).all()
    original_hosts = runtime_session.exec(select(HostRecord)).all()
    vm_host = next(host for host in original_hosts if host.ip == "172.20.10.2")
    windows_host = next(host for host in original_hosts if host.ip == "172.20.10.8")
    for scan_host in scan_hosts:
        scan_host.host_id = windows_host.id
    runtime_session.flush()

    assert repair_ambiguous_mac_identities(runtime_session) == 1

    repaired_hosts = runtime_session.exec(select(HostRecord)).all()
    repaired_by_ip = {host.ip: host for host in repaired_hosts}
    assert repaired_by_ip["172.20.10.8"].id == windows_host.id
    assert repaired_by_ip["172.20.10.2"].operating_system_json["name"] == "Linux"
    assert repaired_by_ip["172.20.10.8"].operating_system_json["name"] == "Windows 11"
    repaired_scan_hosts = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
    ).all()
    assert {item.ip: item.host_id for item in repaired_scan_hosts} == {
        "172.20.10.2": vm_host.id,
        "172.20.10.8": windows_host.id,
    }
    assert repair_ambiguous_mac_identities(runtime_session) == 0


def test_mac_absent_scan_host_resolves_by_ip(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    timestamp_a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamp_b = datetime(2026, 2, 1, tzinfo=timezone.utc)

    scan_a = _scan(uuid4(), timestamp_a, [_host("192.168.1.20", None)])
    scan_b = _scan(uuid4(), timestamp_b, [_host("192.168.1.20", None)])

    _persist(runtime_session, scan_a, seeded_org, provisioned_agent)
    _persist(runtime_session, scan_b, seeded_org, provisioned_agent)

    hosts = runtime_session.exec(select(HostRecord)).all()
    assert len(hosts) == 1
    assert hosts[0].first_seen_at == timestamp_a
    assert hosts[0].last_seen_at == timestamp_b


def test_unknown_vendor_does_not_replace_known_vendor_for_same_mac(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    timestamp_a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamp_b = datetime(2026, 2, 1, tzinfo=timezone.utc)
    ip = "192.168.1.25"
    mac = "00:00:00:00:00:01"
    _persist(
        runtime_session,
        _scan(uuid4(), timestamp_a, [_host(ip, mac, vendor="Known vendor")]),
        seeded_org,
        provisioned_agent,
    )
    _persist(
        runtime_session,
        _scan(uuid4(), timestamp_b, [_host(ip, mac, vendor="unknown")]),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(
        select(HostRecord).where(
            HostRecord.org_id == seeded_org.id, HostRecord.mac == mac
        )
    ).one()
    assert host.last_seen_at == timestamp_b
    assert host.vendor == "Known vendor"


def test_host_only_in_latest_scan_has_first_seen_equal_latest(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    timestamp_a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamp_b = datetime(2026, 2, 1, tzinfo=timezone.utc)

    scan_a = _scan(uuid4(), timestamp_a, [_host("192.168.1.30", "11:22:33:44:55:66")])
    scan_b = _scan(uuid4(), timestamp_b, [_host("192.168.1.31", "77:88:99:AA:BB:CC")])

    _persist(runtime_session, scan_a, seeded_org, provisioned_agent)
    _persist(runtime_session, scan_b, seeded_org, provisioned_agent)

    hosts = runtime_session.exec(select(HostRecord)).all()
    new_host = next(h for h in hosts if h.mac == "77:88:99:AA:BB:CC")
    assert new_host.first_seen_at == timestamp_b
    assert new_host.last_seen_at == timestamp_b


def test_every_scan_host_gets_host_id_assigned(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    scan = _scan(
        uuid4(),
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        [
            _host("192.168.1.40", "01:02:03:04:05:06"),
            _host("192.168.1.41", None),
        ],
    )

    _persist(runtime_session, scan, seeded_org, provisioned_agent)

    scan_hosts = runtime_session.exec(select(ScanHostRecord)).all()
    assert len(scan_hosts) == 2
    assert all(sh.host_id is not None for sh in scan_hosts)


def test_newer_missing_detection_preserves_last_supported_inventory_value(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    mac = "AA:BB:CC:DD:EE:01"
    first_scan_id = uuid4()
    second_scan_id = uuid4()
    second_timestamp = datetime(2026, 2, 1, tzinfo=timezone.utc)
    _persist(
        runtime_session,
        _scan(
            first_scan_id,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            [_host("192.168.1.50", mac, operating_system=_os("Linux 5", 96))],
        ),
        seeded_org,
        provisioned_agent,
    )
    _persist(
        runtime_session,
        _scan(
            second_scan_id,
            second_timestamp,
            [_host("192.168.1.50", mac, hostname="new-name")],
        ),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(select(HostRecord)).one()
    latest_scan_host = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == second_scan_id)
    ).one()
    assert host.operating_system_json == _os("Linux 5", 96)
    assert host.hostname == "new-name"
    assert host.last_seen_at == second_timestamp
    assert latest_scan_host.operating_system_json is None


def test_newer_supported_detection_refreshes_inventory_value(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    mac = "AA:BB:CC:DD:EE:02"
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            [_host("192.168.1.51", mac, operating_system=_os("Linux 4", 90))],
        ),
        seeded_org,
        provisioned_agent,
    )
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            [_host("192.168.1.51", mac, operating_system=_os("Linux 5", 95))],
        ),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(select(HostRecord)).one()
    assert host.operating_system_json == _os("Linux 5", 95)


def test_late_older_detection_does_not_replace_inventory_value(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    mac = "AA:BB:CC:DD:EE:03"
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            [_host("192.168.1.52", mac, operating_system=_os("Linux 6", 98))],
        ),
        seeded_org,
        provisioned_agent,
    )
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            [_host("192.168.1.52", mac, operating_system=_os("Linux 4", 90))],
        ),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(select(HostRecord)).one()
    assert host.operating_system_json == _os("Linux 6", 98)


def test_first_scan_without_detection_materialises_null_inventory_value(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            [_host("192.168.1.53", None)],
        ),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(select(HostRecord)).one()
    assert host.operating_system_json is None


def test_first_supported_detection_materialises_exact_inventory_value(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    operating_system = _os("Linux 5", 96)
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            [_host("192.168.1.54", None, operating_system=operating_system)],
        ),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(select(HostRecord)).one()
    assert host.operating_system_json == operating_system


def test_first_supported_detection_after_absence_populates_inventory_value(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    mac = "AA:BB:CC:DD:EE:04"
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            [_host("192.168.1.55", mac)],
        ),
        seeded_org,
        provisioned_agent,
    )
    operating_system = _os("Linux 5", 96)
    _persist(
        runtime_session,
        _scan(
            uuid4(),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            [_host("192.168.1.55", mac, operating_system=operating_system)],
        ),
        seeded_org,
        provisioned_agent,
    )

    host = runtime_session.exec(select(HostRecord)).one()
    assert host.operating_system_json == operating_system
