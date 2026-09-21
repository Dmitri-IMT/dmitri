from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from api.models.persistence import (
    ExposureRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.services.inventory import reconcile_scan_inventory
from api.services.read import get_host_detail
from read_factories import make_org, seed_read_graph
from sqlmodel import Session
from starlette.testclient import TestClient


def _add_host(
    session: Session,
    org_id,
    *,
    ip: str,
    hostname: str,
    vendor: str,
    last_seen_at: datetime | None = None,
    vulnerability_count: int = 0,
) -> HostRecord:
    now = datetime.now(timezone.utc)
    host = HostRecord(
        identity_key=f"sortable-{ip}",
        org_id=org_id,
        ip=ip,
        mac=None,
        hostname=hostname,
        vendor=vendor,
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=now,
        last_seen_at=last_seen_at or now,
        vulnerability_count=vulnerability_count,
    )
    session.add(host)
    session.commit()
    session.refresh(host)
    return host


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_list_hosts_happy_path(
    client: TestClient,
    administrative_session: Session,
    bearer_headers,
    role: str,
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        "/api/v1/hosts", headers=bearer_headers(seeded["org"].id, role)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    host_ids = {row["host_id"] for row in body["data"]}
    assert host_ids == {str(seeded["host"].id), str(seeded["other_host"].id)}
    seeded_row = next(
        row for row in body["data"] if row["host_id"] == str(seeded["host"].id)
    )
    assert (
        datetime.fromisoformat(seeded_row["first_seen_at"])
        == seeded["host"].first_seen_at
    )


def test_list_hosts_pages_beyond_the_first_twenty(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    now = datetime.now(timezone.utc)
    for index in range(23):
        administrative_session.add(
            HostRecord(
                identity_key=f"paging-{index}",
                org_id=seeded["org"].id,
                ip=f"192.168.9.{index + 1}",
                mac=f"aa:bb:cc:00:00:{index:02x}",
                hostname=f"paged-host-{index}",
                vendor="Acme",
                open_ports_count=0,
                highest_severity=None,
                first_seen_at=now,
                last_seen_at=now - timedelta(minutes=index + 1),
            )
        )
    administrative_session.commit()

    headers = bearer_headers(seeded["org"].id, "admin")
    first = client.get("/api/v1/hosts?page=1&per_page=20", headers=headers)
    second = client.get("/api/v1/hosts?page=2&per_page=20", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()

    assert first_body["total"] == 25
    assert second_body["total"] == 25
    assert len(first_body["data"]) == 20
    assert len(second_body["data"]) == 5
    assert second_body["page"] == 2

    first_ids = {row["host_id"] for row in first_body["data"]}
    second_ids = {row["host_id"] for row in second_body["data"]}
    assert first_ids.isdisjoint(second_ids)
    assert len(first_ids | second_ids) == 25


def test_list_hosts_sorts_by_hostname_ascending(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    _add_host(
        administrative_session,
        seeded["org"].id,
        ip="192.168.1.30",
        hostname="aaa",
        vendor="Zeta",
    )

    response = client.get(
        "/api/v1/hosts?sort_by=hostname&sort_order=asc",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    hostnames = [row["hostname"] for row in response.json()["data"]]
    assert hostnames == ["aaa", "host-a", "host-b"]


def test_list_hosts_sorts_by_vendor_descending(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    _add_host(
        administrative_session,
        seeded["org"].id,
        ip="192.168.1.30",
        hostname="aaa",
        vendor="Zeta",
    )

    response = client.get(
        "/api/v1/hosts?sort_by=vendor&sort_order=desc",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    vendors = [row["vendor"] for row in response.json()["data"]]
    assert vendors == ["Zeta", "Acme", "Acme"]


def test_list_hosts_sorts_by_ip_numerically_not_lexicographically(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    for ip in ("192.168.2.10", "192.168.2.2", "192.168.2.20"):
        _add_host(
            administrative_session,
            seeded["org"].id,
            ip=ip,
            hostname=f"host-{ip}",
            vendor="Acme",
        )

    response = client.get(
        "/api/v1/hosts?sort_by=ip&sort_order=asc",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    ips = [row["ip"] for row in response.json()["data"]]
    # A text sort would order these .10, .2, .20 -- the cast to INET is what
    # keeps .2 ahead of .10, and only the real dialect compiles that cast.
    assert ips == [
        "192.168.1.10",
        "192.168.1.20",
        "192.168.2.2",
        "192.168.2.10",
        "192.168.2.20",
    ]


def test_list_hosts_without_sort_params_is_last_seen_at_desc(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    older = datetime.now(timezone.utc) - timedelta(hours=1)
    administrative_session.add(
        HostRecord(
            identity_key="older-host",
            org_id=seeded["org"].id,
            ip="192.168.1.40",
            mac=None,
            hostname="older",
            vendor="Acme",
            open_ports_count=0,
            highest_severity=None,
            first_seen_at=older,
            last_seen_at=older,
        )
    )
    administrative_session.commit()

    response = client.get(
        "/api/v1/hosts", headers=bearer_headers(seeded["org"].id, "admin")
    )
    assert response.status_code == 200
    last_seen = [row["last_seen_at"] for row in response.json()["data"]]
    assert last_seen == sorted(last_seen, reverse=True)
    assert response.json()["data"][-1]["hostname"] == "older"


@pytest.mark.parametrize(
    ("query",),
    (
        ("sort_by=not_a_column",),
        ("sort_order=sideways",),
    ),
)
def test_list_hosts_invalid_query_returns_validation_error(
    client: TestClient, administrative_session: Session, bearer_headers, query: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/hosts?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_hosts_pagination_is_disjoint_under_a_non_default_sort(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    for index in range(23):
        _add_host(
            administrative_session,
            seeded["org"].id,
            ip=f"192.168.9.{index + 1}",
            hostname=f"paged-host-{index:02d}",
            vendor="Acme",
        )

    headers = bearer_headers(seeded["org"].id, "admin")
    query = "sort_by=hostname&sort_order=asc"
    first = client.get(f"/api/v1/hosts?page=1&per_page=20&{query}", headers=headers)
    second = client.get(f"/api/v1/hosts?page=2&per_page=20&{query}", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    first_ids = [row["host_id"] for row in first.json()["data"]]
    second_ids = [row["host_id"] for row in second.json()["data"]]

    assert len(first_ids) == 20
    assert len(second_ids) == 5
    assert set(first_ids).isdisjoint(second_ids)
    assert len(set(first_ids) | set(second_ids)) == 25


def test_get_host_by_id_happy_path(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["host_id"] == str(seeded["host"].id)
    assert datetime.fromisoformat(body["first_seen_at"]) == seeded["host"].first_seen_at
    assert datetime.fromisoformat(body["last_seen_at"]) == seeded["host"].last_seen_at
    # Pin the wire format itself: pydantic renders a UTC instant with a "Z"
    # suffix, and that is what the generated frontend client parses.
    assert body["first_seen_at"].endswith("Z")
    assert body["hostname"] == "host-a"
    assert len(body["scan_history"]) == 1
    assert body["scan_history"][0]["scan_id"] == str(seeded["scan"].scan_id)


def test_host_reads_return_inventory_value_and_history_snapshot(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    inventory = {
        "name": "Linux 6",
        "accuracy": 98,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "6.X",
        "device_type": "general purpose",
        "cpes": ["cpe:/o:linux:linux_kernel:6"],
    }
    snapshot = {
        "name": "Linux 5",
        "accuracy": 91,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "5.X",
        "device_type": "general purpose",
        "cpes": ["cpe:/o:linux:linux_kernel:5"],
    }
    seeded["host"].operating_system_json = inventory
    seeded["scan_host"].operating_system_json = snapshot
    administrative_session.commit()
    headers = bearer_headers(seeded["org"].id, "viewer")

    listed = client.get("/api/v1/hosts", headers=headers)
    assert listed.status_code == 200
    list_row = next(
        host
        for host in listed.json()["data"]
        if host["host_id"] == str(seeded["host"].id)
    )
    assert list_row["operating_system"] == inventory

    detail = client.get(f"/api/v1/hosts/{seeded['host'].id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["operating_system"] == inventory
    assert detail.json()["scan_history"][0]["operating_system"] == snapshot


def test_host_read_degrades_malformed_persisted_operating_system(
    administrative_session: Session,
) -> None:
    seeded = seed_read_graph(administrative_session)
    seeded["host"].operating_system_json = {
        "name": "Linux",
        "accuracy": 101,
        "cpes": [],
    }
    administrative_session.commit()

    detail = get_host_detail(
        administrative_session,
        seeded["host"].id,
        org_id=seeded["org"].id,
    )
    assert detail is not None
    assert detail.operating_system is None
    assert "operating_system" in detail.unreadable_fields


def test_host_history_degrades_malformed_persisted_operating_system_snapshot(
    administrative_session: Session,
) -> None:
    seeded = seed_read_graph(administrative_session)
    seeded["scan_host"].operating_system_json = {
        "name": "Linux",
        "accuracy": "high",
        "cpes": [],
    }
    administrative_session.commit()

    detail = get_host_detail(
        administrative_session,
        seeded["host"].id,
        org_id=seeded["org"].id,
    )
    assert detail is not None
    assert detail.scan_history[0].operating_system is None
    assert "operating_system" in detail.unreadable_fields


def test_mac_less_host_is_listed_and_readable(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    now = datetime.now(timezone.utc)
    mac_less = HostRecord(
        identity_key="ip:192.168.1.30",
        org_id=seeded["org"].id,
        ip="192.168.1.30",
        mac=None,
        hostname="host-routed",
        vendor="Unknown",
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=now,
        last_seen_at=now,
    )
    administrative_session.add(mac_less)
    administrative_session.commit()

    headers = bearer_headers(seeded["org"].id, "admin")
    listed = client.get("/api/v1/hosts", headers=headers)
    assert listed.status_code == 200
    row = next(
        item for item in listed.json()["data"] if item["host_id"] == str(mac_less.id)
    )
    assert row["mac"] is None

    detail = client.get(f"/api/v1/hosts/{mac_less.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["mac"] is None


def test_get_host_by_id_unknown_returns_404(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/hosts/{uuid4()}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404


def test_get_host_by_id_cross_org_returns_404_not_403(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/hosts/{seeded['foreign_host'].id}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 404
    assert response.status_code != 403


def test_legacy_host_detail_reports_assessment_unavailable(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["device_profile"] is None
    assert body["assessment_status"] == "unavailable"
    assert body["assessment_policy_version"] is None
    assert body["exposures"] == []


def test_host_detail_uses_latest_scan_profile_and_exposures(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    profile = {
        "manufacturer": "Acme",
        "product_family": "Gateway",
        "model": "GW-1",
        "confidence": "medium",
        "evidence": [],
        "conflicts": [],
        "limitations": [],
    }
    latest = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded["org"].id,
        timestamp=seeded["scan"].timestamp + timedelta(minutes=1),
        subnet="192.168.1.0/24",
        scan_mode="extensive",
        status="completed",
        metadata_json={},
        assessment_policy_version="2026-09-15.1",
    )
    administrative_session.add(latest)
    administrative_session.flush()
    snapshot = ScanHostRecord(
        scan_id=latest.scan_id,
        host_id=seeded["host"].id,
        ip=seeded["host"].ip,
        mac=seeded["host"].mac,
        hostname=seeded["host"].hostname,
        vendor=seeded["host"].vendor,
        machine_type="router",
        device_profile_json=profile,
    )
    administrative_session.add(snapshot)
    administrative_session.flush()
    port = PortRecord(
        scan_host_id=snapshot.id,
        port=443,
        protocol="tcp",
        state="open",
    )
    administrative_session.add(port)
    administrative_session.flush()
    administrative_session.add(
        ExposureRecord(
            scan_id=latest.scan_id,
            scan_host_id=snapshot.id,
            port_id=port.id,
            ip=snapshot.ip,
            port=443,
            protocol="tcp",
            observed_service="https",
            role="administration",
            attention="review",
            confidence="medium",
            reason="administration endpoint",
        )
    )
    seeded["host"].machine_type = "router"
    seeded["host"].device_profile_json = profile
    seeded["host"].device_profile_policy_version = "2026-09-15.1"
    administrative_session.commit()

    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["machine_type"] == "router"
    assert body["device_profile"] == profile
    assert body["assessment_status"] == "available"
    assert body["assessment_policy_version"] == "2026-09-15.1"
    assert [(row["port"], row["protocol"]) for row in body["exposures"]] == [
        (443, "tcp")
    ]
    assert body["vulnerability_count"] == seeded["host"].vulnerability_count


def test_host_detail_tie_break_keeps_profile_and_exposures_on_one_scan(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    ts = seeded["scan"].timestamp + timedelta(minutes=2)
    created = ts
    winner_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    loser_id = UUID("11111111-1111-4111-8111-111111111111")
    winner_profile = {
        "manufacturer": "Acme",
        "product_family": "Gateway",
        "model": "GW-1",
        "confidence": "medium",
        "evidence": [],
        "conflicts": [],
        "limitations": [],
    }
    loser_profile = {
        "manufacturer": "Synology",
        "product_family": "NAS",
        "model": "DS-1",
        "confidence": "medium",
        "evidence": [],
        "conflicts": [],
        "limitations": [],
    }
    policy = "2026-09-15.1"

    def add_scan(
        scan_id: UUID,
        *,
        machine_type: str,
        profile: dict,
        exposure_port: int,
    ) -> ScanHostRecord:
        scan = ScanRecord(
            scan_id=scan_id,
            org_id=seeded["org"].id,
            timestamp=ts,
            subnet="192.168.1.0/24",
            scan_mode="extensive",
            status="completed",
            metadata_json={},
            assessment_policy_version=policy,
            created_at=created,
        )
        administrative_session.add(scan)
        administrative_session.flush()
        snapshot = ScanHostRecord(
            scan_id=scan.scan_id,
            host_id=seeded["host"].id,
            ip=seeded["host"].ip,
            mac=seeded["host"].mac,
            hostname=seeded["host"].hostname,
            vendor=seeded["host"].vendor,
            machine_type=machine_type,
            device_profile_json=profile,
        )
        administrative_session.add(snapshot)
        administrative_session.flush()
        port = PortRecord(
            scan_host_id=snapshot.id,
            port=exposure_port,
            protocol="tcp",
            state="open",
        )
        administrative_session.add(port)
        administrative_session.flush()
        administrative_session.add(
            ExposureRecord(
                scan_id=scan.scan_id,
                scan_host_id=snapshot.id,
                port_id=port.id,
                ip=snapshot.ip,
                port=exposure_port,
                protocol="tcp",
                observed_service="https",
                role="administration",
                attention="review",
                confidence="medium",
                reason="administration endpoint",
            )
        )
        return snapshot

    add_scan(
        winner_id, machine_type="router", profile=winner_profile, exposure_port=443
    )
    add_scan(
        loser_id, machine_type="storage", profile=loser_profile, exposure_port=80
    )
    administrative_session.commit()

    reconcile_scan_inventory(
        administrative_session, administrative_session.get(ScanRecord, winner_id)
    )
    reconcile_scan_inventory(
        administrative_session, administrative_session.get(ScanRecord, loser_id)
    )
    seeded["host"].machine_type = "storage"
    seeded["host"].device_profile_json = loser_profile
    seeded["host"].device_profile_policy_version = policy
    administrative_session.commit()

    detail = get_host_detail(
        administrative_session,
        seeded["host"].id,
        org_id=seeded["org"].id,
    )
    assert detail is not None
    assert detail.machine_type == "router"
    assert detail.device_profile is not None
    assert detail.device_profile.model_dump(mode="json") == winner_profile
    assert detail.assessment_policy_version == policy
    assert [(row.port, row.protocol) for row in detail.exposures] == [(443, "tcp")]

    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["machine_type"] == "router"
    assert body["device_profile"] == winner_profile
    assert body["assessment_policy_version"] == policy
    assert [(row["port"], row["protocol"]) for row in body["exposures"]] == [
        (443, "tcp")
    ]


def test_quiet_total_is_the_whole_inventory_on_every_page_and_both_groups(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    org = make_org(administrative_session, "Quiet Whole Inventory")
    now = datetime.now(timezone.utc)
    quiet_ids = set()
    for index in range(45):
        is_quiet = index < 6
        host = _add_host(
            administrative_session,
            org.id,
            ip=f"192.168.7.{index + 1}",
            hostname=f"machine-{index:02d}",
            vendor="Acme",
            last_seen_at=now - timedelta(days=8 if is_quiet else 1),
        )
        if is_quiet:
            quiet_ids.add(str(host.id))

    headers = bearer_headers(org.id, "admin")
    active_pages = [
        client.get(f"/api/v1/hosts?page={page}&per_page=20", headers=headers).json()
        for page in (1, 2, 3)
    ]
    quiet_page = client.get(
        "/api/v1/hosts?group=quiet&per_page=20", headers=headers
    ).json()

    assert [len(page["data"]) for page in active_pages] == [20, 19, 0]
    assert [page["total"] for page in active_pages] == [39, 39, 39]
    assert [page["quiet_total"] for page in active_pages] == [6, 6, 6]
    assert quiet_page["quiet_total"] == 6
    assert quiet_page["total"] == 6

    listed = {row["host_id"] for page in active_pages for row in page["data"]}
    assert len(listed) == 39
    assert listed.isdisjoint(quiet_ids)
    assert {row["host_id"] for row in quiet_page["data"]} == quiet_ids


def test_quiet_group_pages_on_its_own_without_disturbing_the_active_list(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    org = make_org(administrative_session, "Quiet Paging")
    now = datetime.now(timezone.utc)
    active_ids = {
        str(
            _add_host(
                administrative_session,
                org.id,
                ip=f"192.168.8.{index + 1}",
                hostname=f"active-{index}",
                vendor="Acme",
                last_seen_at=now - timedelta(days=1),
            ).id
        )
        for index in range(2)
    }
    quiet_ids = {
        str(
            _add_host(
                administrative_session,
                org.id,
                ip=f"192.168.8.{index + 11}",
                hostname=f"quiet-{index}",
                vendor="Acme",
                last_seen_at=now - timedelta(days=10 + index),
            ).id
        )
        for index in range(3)
    }

    headers = bearer_headers(org.id, "admin")
    before = client.get("/api/v1/hosts", headers=headers).json()
    first = client.get(
        "/api/v1/hosts?group=quiet&per_page=2&page=1", headers=headers
    ).json()
    second = client.get(
        "/api/v1/hosts?group=quiet&per_page=2&page=2", headers=headers
    ).json()
    after = client.get("/api/v1/hosts", headers=headers).json()

    assert [len(first["data"]), len(second["data"])] == [2, 1]
    assert first["total"] == 3
    assert first["quiet_total"] == 3
    assert second["page"] == 2
    quiet_listed = {row["host_id"] for row in first["data"] + second["data"]}
    assert quiet_listed == quiet_ids

    assert {row["host_id"] for row in before["data"]} == active_ids
    assert after == before


def test_quiet_threshold_is_seven_days(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    org = make_org(administrative_session, "Quiet Threshold")
    now = datetime.now(timezone.utc)
    eight_days = _add_host(
        administrative_session,
        org.id,
        ip="192.168.6.1",
        hostname="eight-days",
        vendor="Acme",
        last_seen_at=now - timedelta(days=8),
    )
    six_days = _add_host(
        administrative_session,
        org.id,
        ip="192.168.6.2",
        hostname="six-days",
        vendor="Acme",
        last_seen_at=now - timedelta(days=6),
    )

    headers = bearer_headers(org.id, "admin")
    active = client.get("/api/v1/hosts", headers=headers).json()
    quiet = client.get("/api/v1/hosts?group=quiet", headers=headers).json()

    assert [row["host_id"] for row in active["data"]] == [str(six_days.id)]
    assert [row["host_id"] for row in quiet["data"]] == [str(eight_days.id)]
    assert active["quiet_total"] == 1
    assert active["total"] == 1


def test_sort_by_vulnerability_count_ranks_the_whole_network_not_the_page(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    org = make_org(administrative_session, "Worst On The Network")
    now = datetime.now(timezone.utc)
    worst = None
    for index in range(45):
        host = _add_host(
            administrative_session,
            org.id,
            ip=f"192.168.5.{index + 1}",
            hostname=f"machine-{index:02d}",
            vendor="Acme",
            last_seen_at=now - timedelta(minutes=index),
            vulnerability_count=index,
        )
        worst = host

    headers = bearer_headers(org.id, "admin")
    query = "sort_by=vulnerability_count&sort_order=desc&per_page=15"
    pages = [
        client.get(f"/api/v1/hosts?{query}&page={page}", headers=headers).json()
        for page in (1, 2, 3)
    ]

    assert [len(page["data"]) for page in pages] == [15, 15, 15]
    assert pages[0]["data"][0]["host_id"] == str(worst.id)
    assert pages[0]["data"][0]["vulnerability_count"] == 44
    counts = [row["vulnerability_count"] for page in pages for row in page["data"]]
    assert counts == sorted(counts, reverse=True)
    assert counts == list(range(44, -1, -1))
