from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from api.dependencies.agent_auth import AgentIdentity
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import (
    EnrichmentJobRecord,
    FindingRecord,
    HostFindingRecord,
    HostPortRecord,
    HostRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.schemas.scan import (
    CoverageUnitPayload,
    FindingEvidenceObservationPayload,
    FindingPayload,
    HostPayload,
    PortPayload,
    ScanIngestRequest,
)
from api.services import worker
from api.services.enrichment import process_claimed_enrichment_job
from api.services.inventory import (
    reconcile_scan_host_inventory,
    reconcile_scan_inventory,
)
from api.services.nvd import NvdClient
from api.services.persistence import finding_dedupe_key, ingest_scan, persist_scan
from sqlalchemy import event
from sqlmodel import Session, select
from test_ingest_scan import (
    _example_scan,
    _fake_nvd_payload,
    _scan_with_findable_payload,
)

T0 = datetime(2026, 6, 1, 11, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(hours=1)
T2 = T0 + timedelta(hours=2)
T3 = T0 + timedelta(hours=3)
IP = "10.0.0.5"
MAC = "AA:BB:CC:DD:EE:05"


def _port(port: int, service: str, version: str | None = None) -> PortPayload:
    return PortPayload(
        port=port, protocol="tcp", state="open", service=service, version=version
    )


def _host(
    *,
    ip: str = IP,
    mac: str = MAC,
    hostname: str = "machine",
    vendor: str = "Generic Co",
    ports: list[PortPayload] | None = None,
) -> HostPayload:
    return HostPayload(
        ip=ip, mac=mac, hostname=hostname, vendor=vendor, ports=ports or []
    )


def _finding(
    title: str, *, ip: str | None = IP, port: int | None = 22
) -> FindingPayload:
    return FindingPayload(
        ip=ip,
        port=port,
        protocol="tcp" if port is not None else None,
        severity="high",
        title=title,
        description="a problem",
        recommendation="fix it",
        evidence="observed",
    )


def _key(title: str, *, ip: str | None = IP, port: int | None = 22) -> str:
    return finding_dedupe_key(
        ip=ip,
        port=port,
        protocol="tcp" if port is not None else None,
        cve_id=None,
        title=title,
    )


def _request(
    ts: datetime,
    hosts: list[HostPayload],
    findings: list[FindingPayload],
) -> ScanIngestRequest:
    return ScanIngestRequest(
        scan_id=uuid4(),
        timestamp=ts,
        subnet="10.0.0.0/24",
        scan_mode="standard",
        hosts=hosts,
        findings=findings,
        metadata={"partial_result": False},
    )


def _ingest(
    session: Session,
    identity: AgentIdentity,
    *,
    ts: datetime,
    hosts: list[HostPayload],
    findings: list[FindingPayload] | None = None,
) -> ScanRecord:
    return ingest_scan(
        session,
        _request(ts, hosts, findings or []),
        identity=identity,
        now=ts,
    )


def _scan_and_reconcile(
    session: Session,
    identity: AgentIdentity,
    *,
    ts: datetime,
    hosts: list[HostPayload],
    findings: list[FindingPayload] | None = None,
) -> ScanRecord:
    scan_record = _ingest(
        session, identity, ts=ts, hosts=hosts, findings=findings
    )
    reconcile_scan_inventory(session, scan_record)
    session.flush()
    return scan_record


def _identity(seeded_org: Org, provisioned_agent: Agent) -> AgentIdentity:
    return AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)


def _machine(session: Session, ip: str = IP) -> HostRecord:
    return session.exec(select(HostRecord).where(HostRecord.ip == ip)).one()


def _host_finding(
    session: Session, host_id: UUID, dedupe_key: str
) -> HostFindingRecord | None:
    return session.exec(
        select(HostFindingRecord).where(
            HostFindingRecord.host_id == host_id,
            HostFindingRecord.dedupe_key == dedupe_key,
        )
    ).one_or_none()


def _open_keys(session: Session, host_id: UUID) -> set[str]:
    return set(
        session.exec(
            select(HostFindingRecord.dedupe_key).where(
                HostFindingRecord.host_id == host_id,
                HostFindingRecord.fixed_at.is_(None),
            )
        ).all()
    )


def _host_port(session: Session, host_id: UUID, port: int) -> HostPortRecord:
    return session.exec(
        select(HostPortRecord).where(
            HostPortRecord.host_id == host_id,
            HostPortRecord.port == port,
        )
    ).one()


def test_first_seen_is_set_once_and_survives_redetection(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=[_port(22, "ssh")])],
        findings=[_finding("weak ssh")],
    )
    machine = _machine(runtime_session)
    row = _host_finding(runtime_session, machine.id, _key("weak ssh"))
    assert row is not None
    assert row.first_seen_at == T1
    assert row.last_seen_at == T1

    later = _ingest(
        runtime_session,
        identity,
        ts=T2,
        hosts=[_host(ports=[_port(22, "ssh")])],
        findings=[_finding("weak ssh")],
    )
    scan_host = runtime_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == later.scan_id)
    ).one()
    reconcile_scan_host_inventory(runtime_session, scan_host)
    runtime_session.flush()

    runtime_session.refresh(row)
    assert row.first_seen_at == T1
    assert row.last_seen_at == T2


def test_duplicate_finding_keeps_each_distinct_evidence_observation(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    first = _finding("weak tls cipher configuration", port=25)
    first.evidence = "3DES vulnerable to SWEET32"
    second = _finding("weak tls cipher configuration", port=25)
    second.evidence = "DES vulnerable to SWEET32"

    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=[_port(25, "smtp")])],
        findings=[first, second],
    )

    rows = runtime_session.exec(select(FindingRecord)).all()
    assert len(rows) == 1
    assert "3DES vulnerable to SWEET32" in rows[0].evidence
    assert "DES vulnerable to SWEET32" in rows[0].evidence


def test_absent_finding_is_fixed_and_a_returning_one_reopens(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    ports = [_port(22, "ssh")]
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=ports)],
        findings=[_finding("weak ssh")],
    )
    machine = _machine(runtime_session)
    key = _key("weak ssh")

    _scan_and_reconcile(
        runtime_session, identity, ts=T2, hosts=[_host(ports=ports)]
    )
    row = _host_finding(runtime_session, machine.id, key)
    assert row is not None
    assert row.fixed_at == T2
    assert row.first_seen_at == T1
    runtime_session.refresh(machine)
    assert machine.vulnerability_count == 0
    assert _open_keys(runtime_session, machine.id) == set()

    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T3,
        hosts=[_host(ports=ports)],
        findings=[_finding("weak ssh")],
    )
    runtime_session.refresh(row)
    assert row.fixed_at is None
    assert row.first_seen_at == T1
    runtime_session.refresh(machine)
    assert machine.vulnerability_count == 1


def test_partial_scan_does_not_fix_unchecked_finding(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    ports = [_port(22, "ssh")]
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=ports)],
        findings=[_finding("weak ssh")],
    )
    machine = _machine(runtime_session)
    key = _key("weak ssh")

    partial = _request(T2, [_host(ports=ports)], [])
    partial.metadata = {"partial_result": True}
    partial_record = ingest_scan(runtime_session, partial, identity=identity, now=T2)
    reconcile_scan_inventory(runtime_session, partial_record)
    runtime_session.flush()

    row = _host_finding(runtime_session, machine.id, key)
    assert row is not None
    assert row.fixed_at is None
    assert row.last_seen_at == T1
    runtime_session.refresh(machine)
    assert machine.vulnerability_count == 1

    _scan_and_reconcile(
        runtime_session, identity, ts=T3, hosts=[_host(ports=ports)]
    )
    runtime_session.refresh(row)
    assert row.fixed_at == T3


def test_scan_with_a_coverage_gap_does_not_fix_unchecked_finding(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    ports = [_port(22, "ssh")]
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=ports)],
        findings=[_finding("weak ssh")],
    )
    machine = _machine(runtime_session)
    key = _key("weak ssh")

    gap = _request(T2, [_host(ports=ports)], [])
    gap.coverage = [
        CoverageUnitPayload(
            ip=gap.hosts[0].ip,
            stage="deep_inspection",
            outcome="timed_out",
            evidence_source="port_discovery",
        )
    ]
    gap_record = ingest_scan(runtime_session, gap, identity=identity, now=T2)
    reconcile_scan_inventory(runtime_session, gap_record)
    runtime_session.flush()

    row = _host_finding(runtime_session, machine.id, key)
    assert row is not None
    assert row.fixed_at is None


def test_scan_without_partial_result_does_not_fix_unchecked_finding(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    ports = [_port(22, "ssh")]
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=ports)],
        findings=[_finding("weak ssh")],
    )
    machine = _machine(runtime_session)
    key = _key("weak ssh")

    unknown = _request(T2, [_host(ports=ports)], [])
    unknown.metadata = None
    unknown_record = ingest_scan(runtime_session, unknown, identity=identity, now=T2)
    reconcile_scan_inventory(runtime_session, unknown_record)
    runtime_session.flush()

    row = _host_finding(runtime_session, machine.id, key)
    assert row is not None
    assert row.fixed_at is None
    runtime_session.refresh(machine)
    assert machine.vulnerability_count == 1


def test_service_absent_from_latest_scan_keeps_its_older_last_seen(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=[_port(22, "ssh"), _port(8080, "http", "1.0")])],
    )
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T2,
        hosts=[_host(ports=[_port(22, "ssh")])],
    )

    machine = _machine(runtime_session)
    gone = _host_port(runtime_session, machine.id, 8080)
    assert gone.first_seen_at == T1
    assert gone.last_seen_at == T1
    assert gone.service == "http"
    assert _host_port(runtime_session, machine.id, 22).last_seen_at == T2


def test_vulnerability_count_equals_the_open_host_findings(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    ports = [_port(22, "ssh")]
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=ports)],
        findings=[_finding("weak ssh"), _finding("open telnet")],
    )
    machine = _machine(runtime_session)
    assert machine.vulnerability_count == 2

    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T2,
        hosts=[_host(ports=ports)],
        findings=[_finding("open telnet"), _finding("stale tls")],
    )
    runtime_session.refresh(machine)
    open_keys = _open_keys(runtime_session, machine.id)
    assert open_keys == {_key("open telnet"), _key("stale tls")}
    assert machine.vulnerability_count == len(open_keys)


def _scan_and_reconcile_id(
    session: Session,
    identity: AgentIdentity,
    *,
    scan_id: UUID,
    ts: datetime,
    hosts: list[HostPayload],
    findings: list[FindingPayload] | None = None,
) -> ScanRecord:
    scan_record = ingest_scan(
        session,
        ScanIngestRequest(
            scan_id=scan_id,
            timestamp=ts,
            subnet="10.0.0.0/24",
            scan_mode="standard",
            hosts=hosts,
            findings=findings or [],
        ),
        identity=identity,
        now=ts,
    )
    reconcile_scan_inventory(session, scan_record)
    session.flush()
    return scan_record


def test_same_timestamp_later_scan_id_stays_latest_after_older_id_reconcile(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    ts = T2
    winner_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    loser_id = UUID("11111111-1111-4111-8111-111111111111")
    _scan_and_reconcile_id(
        runtime_session,
        identity,
        scan_id=winner_id,
        ts=ts,
        hosts=[_host(vendor="Hikvision", ports=[_port(554, "rtsp")])],
    )
    _scan_and_reconcile_id(
        runtime_session,
        identity,
        scan_id=loser_id,
        ts=ts,
        hosts=[_host(vendor="Generic Co", ports=[_port(22, "ssh")])],
    )
    for scan_id in (winner_id, loser_id):
        row = runtime_session.get(ScanRecord, scan_id)
        assert row is not None
        row.created_at = ts
        runtime_session.add(row)
    runtime_session.flush()
    runtime_session.expire_all()
    reconcile_scan_inventory(
        runtime_session, runtime_session.get(ScanRecord, winner_id)
    )
    reconcile_scan_inventory(
        runtime_session, runtime_session.get(ScanRecord, loser_id)
    )
    assert _machine(runtime_session).machine_type == "camera"


def test_out_of_order_older_scan_lowers_first_seen_and_nothing_else(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T2,
        hosts=[_host(vendor="Hikvision", ports=[_port(554, "rtsp")])],
        findings=[_finding("weak ssh"), _finding("open telnet")],
    )
    machine = _machine(runtime_session)
    assert machine.machine_type == "camera"
    assert machine.vulnerability_count == 2

    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T0,
        hosts=[_host(vendor="Brother", ports=[_port(9100, "jetdirect")])],
        findings=[_finding("weak ssh")],
    )

    untouched = _host_finding(runtime_session, machine.id, _key("open telnet"))
    assert untouched is not None
    assert untouched.fixed_at is None
    runtime_session.refresh(machine)
    assert machine.machine_type == "camera"
    assert machine.vulnerability_count == 2
    lowered = _host_finding(runtime_session, machine.id, _key("weak ssh"))
    assert lowered is not None
    assert lowered.first_seen_at == T0
    assert lowered.last_seen_at == T2


def test_host_less_finding_gets_no_host_finding_row(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[_host(ports=[_port(22, "ssh")])],
        findings=[
            _finding("weak ssh"),
            _finding("subnet has no gateway", ip=None, port=None),
        ],
    )

    machine = _machine(runtime_session)
    global_key = _key("subnet has no gateway", ip=None, port=None)
    assert _host_finding(runtime_session, machine.id, global_key) is None
    assert _open_keys(runtime_session, machine.id) == {_key("weak ssh")}
    assert machine.vulnerability_count == 1


def test_machine_type_written_from_vendor_and_open_services(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    _scan_and_reconcile(
        runtime_session,
        identity,
        ts=T1,
        hosts=[
            _host(vendor="Hikvision", ports=[]),
            _host(
                ip="10.0.0.6",
                mac="AA:BB:CC:DD:EE:06",
                hostname="laptop",
                vendor="Generic Co",
                ports=[_port(22, "ssh")],
            ),
        ],
    )

    assert _machine(runtime_session, IP).machine_type == "camera"
    assert _machine(runtime_session, "10.0.0.6").machine_type == "computer"


def _reconcile_select_count(
    session: Session, identity: AgentIdentity, *, ts: datetime, size: int
) -> int:
    ip = f"10.0.1.{size}"
    host = _host(ip=ip, mac=f"AA:BB:CC:DD:01:{size:02d}", ports=[
        _port(1000 + n, "http") for n in range(size)
    ])
    findings = [
        _finding(f"problem {n}", ip=ip, port=1000 + n) for n in range(size)
    ]
    _scan_and_reconcile(
        session, identity, ts=ts, hosts=[host], findings=findings
    )
    later = _ingest(
        session,
        identity,
        ts=ts + timedelta(minutes=30),
        hosts=[host],
        findings=findings,
    )
    scan_host = session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == later.scan_id)
    ).one()
    session.flush()

    selects: list[str] = []

    def record(conn, cursor, statement, *args) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        reconcile_scan_host_inventory(session, scan_host)
        session.flush()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(selects)


def test_reconcile_query_count_does_not_grow_with_ports_or_findings(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    identity = _identity(seeded_org, provisioned_agent)
    small = _reconcile_select_count(runtime_session, identity, ts=T1, size=2)
    large = _reconcile_select_count(runtime_session, identity, ts=T2, size=12)

    assert large == small


def test_persist_scan_reconciles_machine_inventory_in_one_transaction(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    _, scan = _example_scan()

    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )

    machines = {
        machine.ip: machine
        for machine in runtime_session.exec(
            select(HostRecord).where(HostRecord.org_id == seeded_org.id)
        ).all()
    }
    assert set(machines) == {"192.168.1.10", "192.168.1.40", "192.168.1.50"}

    expected = {
        "192.168.1.10": (2, 1, "camera"),
        "192.168.1.40": (1, 1, "unknown"),
        "192.168.1.50": (1, 0, "sensor"),
    }
    source_profiles = {
        str(host.ip): host.device_profile.model_dump(mode="json")
        for host in scan.hosts
    }
    for ip, (expected_ports, expected_findings, machine_type) in expected.items():
        machine = machines[ip]
        ports = runtime_session.exec(
            select(HostPortRecord).where(HostPortRecord.host_id == machine.id)
        ).all()
        host_findings = runtime_session.exec(
            select(HostFindingRecord).where(
                HostFindingRecord.host_id == machine.id
            )
        ).all()
        assert len(ports) == expected_ports
        assert len(host_findings) == expected_findings
        assert machine.machine_type == machine_type
        assert machine.device_profile_json == source_profiles[ip]
        assert machine.device_profile_policy_version == "2026-09-15.1"
        assert machine.vulnerability_count == expected_findings
        for host_finding in host_findings:
            assert host_finding.first_seen_at == scan.timestamp
            assert host_finding.fixed_at is None


def test_newer_legacy_scan_uses_fallback_and_clears_profile_projection(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    _, current = _example_scan()
    persist_scan(
        runtime_session,
        current,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=current.timestamp,
        existing=None,
    )
    source = current.hosts[0]
    machine = _machine(runtime_session, str(source.ip))
    previous_count = machine.vulnerability_count
    assert machine.device_profile_json is not None

    _scan_and_reconcile(
        runtime_session,
        _identity(seeded_org, provisioned_agent),
        ts=current.timestamp + timedelta(hours=1),
        hosts=[
            _host(
                ip=str(source.ip),
                mac=source.mac or MAC,
                vendor="Hikvision",
                ports=[_port(554, "rtsp")],
            )
        ],
    )

    runtime_session.refresh(machine)
    assert machine.machine_type == "camera"
    assert machine.device_profile_json is None
    assert machine.device_profile_policy_version is None
    assert machine.vulnerability_count == 0
    assert previous_count >= 0


def test_older_legacy_scan_cannot_replace_current_profile_or_counts(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    _, current = _example_scan()
    persist_scan(
        runtime_session,
        current,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=current.timestamp,
        existing=None,
    )
    source = current.hosts[0]
    machine = _machine(runtime_session, str(source.ip))
    before = (
        machine.machine_type,
        machine.device_profile_json,
        machine.device_profile_policy_version,
        machine.vulnerability_count,
    )

    _scan_and_reconcile(
        runtime_session,
        _identity(seeded_org, provisioned_agent),
        ts=current.timestamp - timedelta(hours=1),
        hosts=[
            _host(
                ip=str(source.ip),
                mac=source.mac or MAC,
                vendor="Brother",
                ports=[_port(9100, "jetdirect")],
            )
        ],
        findings=[_finding("older finding", ip=str(source.ip), port=9100)],
    )

    runtime_session.refresh(machine)
    assert (
        machine.machine_type,
        machine.device_profile_json,
        machine.device_profile_policy_version,
        machine.vulnerability_count,
    ) == before


def test_cpe_enrichment_finding_reaches_machine_inventory(
    monkeypatch, runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:  # type: ignore[no-untyped-def]
    scan_id = uuid4()
    scan = _scan_with_findable_payload(scan_id)
    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )
    machine = runtime_session.exec(
        select(HostRecord).where(HostRecord.ip == "10.0.0.99")
    ).one()
    assert machine.vulnerability_count == 0
    assert (
        runtime_session.exec(
            select(HostFindingRecord).where(
                HostFindingRecord.host_id == machine.id
            )
        ).first()
        is None
    )

    monkeypatch.setattr(
        NvdClient,
        "query_by_cpe",
        lambda self, session, cpe: _fake_nvd_payload("CVE-2016-10012"),
    )
    monkeypatch.setattr(worker, "get_session", lambda: iter([runtime_session]))
    assert worker.run_worker_once(batch_size=25) == 1

    runtime_session.refresh(machine)
    host_findings = runtime_session.exec(
        select(HostFindingRecord).where(HostFindingRecord.host_id == machine.id)
    ).all()
    assert len(host_findings) == 1
    assert host_findings[0].first_seen_at == scan.timestamp
    assert host_findings[0].fixed_at is None
    assert machine.vulnerability_count == 1


def _scan_with_cve_finding(scan_id) -> ScanIngestRequest:
    host = HostPayload(
        ip="10.0.0.77",
        mac=None,
        hostname="host",
        vendor="vendor",
        ports=[
            PortPayload(
                port=22, protocol="tcp", state="open", service="ssh", cpes=[]
            )
        ],
    )
    finding = FindingPayload(
        ip="10.0.0.77",
        port=22,
        protocol="tcp",
        service="ssh",
        source="nmap_vulners",
        cve_id="CVE-2016-10012",
        cvss_score=4.0,
        severity="medium",
        title="OpenSSH version mapped to known CVE",
        description="a problem",
        recommendation="fix it",
        evidence="observed",
    )
    return ScanIngestRequest(
        scan_id=scan_id,
        timestamp=datetime.now(timezone.utc),
        subnet="10.0.0.0/24",
        scan_mode="standard",
        hosts=[host],
        findings=[finding],
    )


def test_cve_enrichment_leaves_machine_inventory_untouched(
    monkeypatch, runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:  # type: ignore[no-untyped-def]
    scan_id = uuid4()
    scan = _scan_with_cve_finding(scan_id)
    persist_scan(
        runtime_session,
        scan,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        command=None,
        now=datetime.now(timezone.utc),
        existing=None,
    )
    machine = runtime_session.exec(
        select(HostRecord).where(HostRecord.ip == "10.0.0.77")
    ).one()
    host_finding = runtime_session.exec(
        select(HostFindingRecord).where(HostFindingRecord.host_id == machine.id)
    ).one()
    before = (
        machine.vulnerability_count,
        host_finding.first_seen_at,
        host_finding.last_seen_at,
        host_finding.fixed_at,
    )
    assert before[0] == 1

    monkeypatch.setattr(
        NvdClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_nvd_payload(cve_id),
    )
    job = runtime_session.exec(
        select(EnrichmentJobRecord).where(
            EnrichmentJobRecord.scan_id == scan_id,
            EnrichmentJobRecord.job_type == "nvd_cve",
        )
    ).one()
    process_claimed_enrichment_job(runtime_session, job)

    finding = runtime_session.exec(
        select(FindingRecord).where(FindingRecord.scan_id == scan_id)
    ).one()
    runtime_session.refresh(machine)
    runtime_session.refresh(host_finding)
    assert finding.cvss_score == 8.1
    assert finding.confidence == "probable"
    assert "target applicability is unverified" in finding.evidence
    assert (
        machine.vulnerability_count,
        host_finding.first_seen_at,
        host_finding.last_seen_at,
        host_finding.fixed_at,
    ) == before


def test_unknown_standalone_evidence_does_not_close_historical_finding(
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    first_scan = _request(
        T0,
        [_host()],
        [
            _finding("Existing service issue"),
            _finding("Unrelated service issue", port=23),
        ],
    )
    ingest_scan(runtime_session, first_scan, identity=identity, now=T0)
    machine = runtime_session.exec(
        select(HostRecord).where(HostRecord.ip == IP)
    ).one()
    histories = runtime_session.exec(
        select(HostFindingRecord).where(HostFindingRecord.host_id == machine.id)
    ).all()
    history = next(
        row
        for row in histories
        if row.dedupe_key.endswith("|22|na|existing service issue")
    )
    unrelated = next(
        row
        for row in histories
        if row.dedupe_key.endswith("|23|na|unrelated service issue")
    )

    unknown = FindingEvidenceObservationPayload(
        ip=IP,
        port=22,
        protocol="tcp",
        condition_key="service:unknown-check",
        method="specific_check",
        result="negative",
        source="nmap_nse",
        source_script="unreviewed-check",
        rule_id="nse:unreviewed-check",
        rule_version="1",
        evidence="The response did not match a supported rule.",
        facts={"state": "not_vulnerable"},
    )
    second_scan = ScanIngestRequest(
        scan_id=uuid4(),
        timestamp=T1,
        subnet="10.0.0.0/24",
        scan_mode="standard",
        hosts=[_host()],
        findings=[],
        metadata={"partial_result": False},
        finding_evidence_policy_version="1",
        finding_observations=[unknown],
    )
    ingest_scan(runtime_session, second_scan, identity=identity, now=T1)
    runtime_session.refresh(history)
    runtime_session.refresh(unrelated)
    assert history.fixed_at is None
    assert unrelated.fixed_at == T1


@pytest.mark.parametrize(
    "missing_dimension", ["ip", "protocol", "port", "unit_id", "all"]
)
def test_unsupported_observation_with_missing_dimension_preserves_only_possible_history(
    missing_dimension: str,
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    issue_key = "smb:signing"
    finding = _finding("SMB signing is optional", port=445).model_copy(
        update={"issue_key": issue_key, "unit_id": 7}
    )
    unrelated_port = 445 if missing_dimension == "port" else 446
    unrelated_finding = _finding(
        "Unrelated SMB signing issue", port=unrelated_port
    ).model_copy(update={"issue_key": issue_key, "unit_id": 7})
    if missing_dimension == "port":
        unrelated_finding.protocol = "udp"
    ingest_scan(
        runtime_session,
        _request(
            T0,
            [_host(ports=[_port(445, "microsoft-ds")])],
            [finding, unrelated_finding],
        ),
        identity=identity,
        now=T0,
    )
    machine = runtime_session.exec(select(HostRecord).where(HostRecord.ip == IP)).one()
    histories = runtime_session.exec(
        select(HostFindingRecord).where(HostFindingRecord.host_id == machine.id)
    ).all()
    history = next(
        row
        for row in histories
        if row.dedupe_key.endswith("|smb signing is optional")
    )
    unrelated = next(
        row for row in histories if row.dedupe_key != history.dedupe_key
    )
    endpoint = {"ip": IP, "protocol": "tcp", "port": 445, "unit_id": 7}
    if missing_dimension == "all":
        endpoint = {key: None for key in endpoint}
    else:
        endpoint[missing_dimension] = None
    unknown = FindingEvidenceObservationPayload(
        ip=endpoint["ip"],
        protocol=endpoint["protocol"],
        port=endpoint["port"],
        unit_id=endpoint["unit_id"],
        condition_key=issue_key,
        method="configuration_observation",
        result="negative",
        source="nmap_nse",
        source_script="smb2-security-mode",
        rule_id="nse:smb2-security-mode",
        rule_version="1",
        evidence="The incomplete observation lacks endpoint scope.",
        facts={},
    )
    second_scan = _request(T1, [_host()], [])
    second_scan.finding_evidence_policy_version = "1"
    second_scan.finding_observations = [unknown]
    ingest_scan(runtime_session, second_scan, identity=identity, now=T1)
    runtime_session.refresh(history)
    runtime_session.refresh(unrelated)
    assert history.fixed_at is None
    assert unrelated.fixed_at == (None if missing_dimension == "all" else T1)


def test_supported_ms17_negative_does_not_close_matching_historical_finding(
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    cve_id = "CVE-2017-0143"
    finding = FindingPayload(
        ip=IP,
        port=445,
        protocol="tcp",
        issue_key=None,
        cve_id=cve_id,
        severity="high",
        title="MS17-010 exposure",
        description="The SMB endpoint is vulnerable.",
        recommendation="Patch the host.",
        evidence="A vulnerable response was observed.",
    )
    ingest_scan(
        runtime_session,
        _request(T0, [_host(ports=[_port(445, "microsoft-ds")])], [finding]),
        identity=identity,
        now=T0,
    )
    machine = runtime_session.exec(
        select(HostRecord).where(HostRecord.ip == IP)
    ).one()
    history = runtime_session.exec(
        select(HostFindingRecord).where(HostFindingRecord.host_id == machine.id)
    ).one()
    negative = FindingEvidenceObservationPayload(
        ip=IP,
        port=445,
        protocol="tcp",
        condition_key=cve_id,
        method="specific_check",
        result="negative",
        source="nmap_nse",
        source_script="smb-vuln-ms17-010",
        rule_id="nse:smb-vuln-ms17-010",
        rule_version="1",
        evidence="The MS17-010 check returned NOT VULNERABLE.",
        facts={
            "vulnerability_state": "NOT VULNERABLE",
            "table": "smb-vuln-ms17-010",
        },
    )
    second_scan = _request(T1, [_host(ports=[_port(445, "microsoft-ds")])], [])
    second_scan.finding_evidence_policy_version = "1"
    second_scan.finding_observations = [negative]
    ingest_scan(runtime_session, second_scan, identity=identity, now=T1)
    runtime_session.refresh(history)
    assert history.fixed_at is None


def test_smb_signing_negative_uses_persisted_issue_key_binding(
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    identity = AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id)
    condition = "smb:signing"
    positive = FindingEvidenceObservationPayload(
        ip=IP,
        port=445,
        protocol="tcp",
        condition_key=condition,
        method="configuration_observation",
        result="positive",
        source="nmap_nse",
        source_script="smb2-security-mode",
        rule_id="nse:smb2-security-mode",
        rule_version="1",
        evidence="Signing is not required.",
        facts={"signing_required": False},
    )
    finding = FindingPayload(
        ip=IP,
        port=445,
        protocol="tcp",
        issue_key=condition,
        severity="high",
        title="SMB signing is optional",
        description="SMB does not require signing.",
        recommendation="Require signing.",
        evidence="Signing is not required.",
        evidence_observations=[positive],
    )
    first = ScanIngestRequest(
        scan_id=uuid4(),
        timestamp=T0,
        subnet="10.0.0.0/24",
        scan_mode="standard",
        hosts=[_host(ports=[_port(445, "microsoft-ds")])],
        findings=[finding],
        metadata={"partial_result": False},
        finding_evidence_policy_version="1",
    )
    ingest_scan(runtime_session, first, identity=identity, now=T0)
    history = runtime_session.exec(select(HostFindingRecord)).one()
    negative = positive.model_copy(
        update={
            "result": "negative",
            "evidence": "Signing is required.",
            "facts": {"signing_required": True},
        }
    )
    second = _request(T1, [_host(ports=[_port(445, "microsoft-ds")])], [])
    second.finding_evidence_policy_version = "1"
    second.finding_observations = [negative]
    ingest_scan(runtime_session, second, identity=identity, now=T1)
    runtime_session.refresh(history)
    assert history.fixed_at is None
