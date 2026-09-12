from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from api.dependencies.agent_auth import AgentIdentity
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import (
    HostFindingRecord,
    HostPortRecord,
    HostRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.schemas.scan import (
    FindingPayload,
    HostPayload,
    PortPayload,
    ScanIngestRequest,
)
from api.services.inventory import (
    reconcile_scan_host_inventory,
    reconcile_scan_inventory,
)
from api.services.persistence import finding_dedupe_key, ingest_scan
from sqlmodel import Session, select

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
