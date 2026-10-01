from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.activity import ActivityRecord
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import (
    EnrichmentJobRecord,
    FindingRecord,
    ScanHostRecord,
    ScanRecord,
    utc_now,
)
from api.services import commands, device_sig
from fastapi.testclient import TestClient
from sqlmodel import Session, select

PATH = "/api/v1/scans"


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _headers(
    *,
    private_key: bytes,
    device_id,
    body: bytes,
    timestamp=None,
    nonce: str | None = None,
) -> dict[str, str]:
    timestamp_str = (timestamp or utc_now()).isoformat()
    nonce_value = nonce or uuid4().hex
    body_hash = device_sig.body_sha256(body)
    canonical = device_sig.canonical_string(
        "POST", PATH, str(device_id), timestamp_str, nonce_value, body_hash
    )
    signature = device_sig.sign(private_key, canonical)
    return {
        "Content-Type": "application/json",
        "X-Device-Id": str(device_id),
        "X-Timestamp": timestamp_str,
        "X-Nonce": nonce_value,
        "X-Body-SHA256": body_hash,
        "X-Signature": signature,
    }


def _host(ip: str = "10.0.0.5") -> dict:
    return {
        "ip": ip,
        "mac": None,
        "hostname": "host-a",
        "vendor": "vendor",
        "ports": [
            {
                "port": 22,
                "protocol": "tcp",
                "state": "open",
                "service": "ssh",
            }
        ],
    }


def _finding(ip: str = "10.0.0.5") -> dict:
    return {
        "ip": ip,
        "port": 22,
        "protocol": "tcp",
        "service": "ssh",
        "severity": "high",
        "title": "Weak SSH configuration",
        "description": "SSH server permits weak ciphers.",
        "recommendation": "Disable weak ciphers.",
        "evidence": "nmap output lists weak cipher suites.",
    }


def _payload(scan_id, *, hosts=None, findings=None) -> dict:
    return {
        "scan_id": str(scan_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subnet": "192.168.1.0/24",
        "scan_mode": "standard",
        "hosts": hosts if hosts is not None else [],
        "findings": findings if findings is not None else [],
    }


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def _post(
    client: TestClient, *, private_key: bytes, device_id, payload: dict, **kwargs
):
    body = _body(payload)
    headers = _headers(
        private_key=private_key, device_id=device_id, body=body, **kwargs
    )
    return client.post(PATH, headers=headers, content=body)


def _seed_placeholder(
    session: Session, *, org_id, agent_id, scan_id, now: datetime
) -> Command:
    scan_record = ScanRecord(
        scan_id=scan_id,
        org_id=org_id,
        timestamp=now,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    session.add(scan_record)
    session.commit()
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status="delivered",
        delivered_at=now,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def _seed_agent(session: Session, org_id) -> tuple[Agent, bytes]:
    private_key, public_key = device_sig.generate_keypair()
    agent = Agent(org_id=org_id, display_name=f"agent-{uuid4()}", public_key=public_key)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent, private_key


def _seed_org(session: Session) -> Org:
    org = Org(name=f"org-{uuid4()}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def test_fills_requested_scan_and_links_agent(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
) -> None:
    private_key, _ = agent_keypair
    now = utc_now()
    scan_id = uuid4()
    _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    payload = _payload(scan_id, hosts=[_host()], findings=[_finding()])

    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 202
    scan_record = administrative_session.get(ScanRecord, scan_id)
    administrative_session.refresh(scan_record)
    assert scan_record.org_id == seeded_org.id
    assert scan_record.agent_id == provisioned_agent.id
    assert scan_record.status == "completed"
    assert administrative_session.exec(select(ScanRecord)).all() == [scan_record]


def test_request_and_scan_both_complete(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
) -> None:
    private_key, _ = agent_keypair
    now = utc_now()
    scan_id = uuid4()
    command = _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    payload = _payload(scan_id)

    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 202
    administrative_session.refresh(command)
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert command.status == "done"
    assert scan_record.status == "completed"
    activity = administrative_session.exec(
        select(ActivityRecord).where(
            ActivityRecord.org_id == seeded_org.id,
            ActivityRecord.subject_id == scan_id,
        )
    ).all()
    assert [row.kind for row in activity].count("scan_finished") == 1
    assert "scan_cancelled" not in [row.kind for row in activity]


def test_late_partial_upload_after_offline_cancel_is_accepted(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
) -> None:
    private_key, _ = agent_keypair
    now = utc_now()
    scan_id = uuid4()
    command = _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )

    asyncio.run(
        commands.cancel_command(
            administrative_session,
            org_id=seeded_org.id,
            command_id=command.id,
            now=now,
        )
    )
    administrative_session.refresh(command)
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert command.status == "cancelled"
    assert scan_record.status == "cancelled"

    payload = _payload(scan_id, hosts=[_host()], findings=[_finding()])
    payload["metadata"] = {"terminated_by": "user_cancel"}
    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 202
    administrative_session.refresh(command)
    administrative_session.refresh(scan_record)
    assert command.status == "cancelled"
    assert scan_record.status == "completed"
    assert len(
        administrative_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).all()
    ) == 1
    activity = administrative_session.exec(
        select(ActivityRecord).where(
            ActivityRecord.org_id == seeded_org.id,
            ActivityRecord.subject_id == scan_id,
        )
    ).all()
    assert [row.kind for row in activity].count("scan_cancelled") == 1
    assert "scan_finished" not in [row.kind for row in activity]


def test_late_progress_report_after_completion_is_a_no_op(
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
) -> None:
    now = utc_now()
    scan_id = uuid4()
    command = _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="done",
        now=now,
    )
    assert applied is True

    late_applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="running",
        now=now + timedelta(seconds=5),
    )

    assert late_applied is False
    administrative_session.refresh(command)
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert command.status == "done"
    assert scan_record.status == "completed"


def test_unrequested_scan_recorded_complete_with_no_command(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
) -> None:
    private_key, _ = agent_keypair
    scan_id = uuid4()
    payload = _payload(scan_id, hosts=[_host()], findings=[_finding()])

    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 202
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert scan_record.org_id == seeded_org.id
    assert scan_record.agent_id == provisioned_agent.id
    assert scan_record.status == "completed"
    assert (
        administrative_session.exec(
            select(Command).where(Command.scan_id == scan_id)
        ).first()
        is None
    )


def test_missing_header_refused_401(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    payload = _payload(uuid4())
    body = _body(payload)
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=body
    )
    del headers["X-Nonce"]

    response = client.post(PATH, headers=headers, content=body)

    assert response.status_code == 401
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_wrong_key_refused_401(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
) -> None:
    other_private_key, _ = device_sig.generate_keypair()
    payload = _payload(uuid4())

    response = _post(
        client,
        private_key=other_private_key,
        device_id=provisioned_agent.id,
        payload=payload,
    )

    assert response.status_code == 401
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_stale_timestamp_refused_401(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    payload = _payload(uuid4())

    response = _post(
        client,
        private_key=private_key,
        device_id=provisioned_agent.id,
        payload=payload,
        timestamp=utc_now() - timedelta(minutes=6),
    )

    assert response.status_code == 401
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_revoked_device_refused_403(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    provisioned_agent.revoked_at = utc_now()
    administrative_session.add(provisioned_agent)
    administrative_session.commit()
    payload = _payload(uuid4())

    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 403
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_another_devices_placeholder_refused_403_and_untouched(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
) -> None:
    other_agent, other_private_key = _seed_agent(administrative_session, seeded_org.id)
    now = utc_now()
    scan_id = uuid4()
    command = _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    payload = _payload(scan_id, hosts=[_host()])

    response = _post(
        client, private_key=other_private_key, device_id=other_agent.id, payload=payload
    )

    assert response.status_code == 403
    administrative_session.refresh(command)
    assert command.status == "delivered"
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert scan_record.status == "pending"
    assert (
        administrative_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )


def test_cross_org_isolation(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
) -> None:
    private_key, _ = agent_keypair
    other_org = _seed_org(administrative_session)
    other_agent, other_private_key = _seed_agent(administrative_session, other_org.id)

    payload_a = _payload(uuid4(), hosts=[_host("10.0.0.5")])
    response_a = _post(
        client,
        private_key=private_key,
        device_id=provisioned_agent.id,
        payload=payload_a,
    )
    payload_b = _payload(uuid4(), hosts=[_host("10.0.0.6")])
    response_b = _post(
        client,
        private_key=other_private_key,
        device_id=other_agent.id,
        payload=payload_b,
    )

    assert response_a.status_code == 202
    assert response_b.status_code == 202
    records = administrative_session.exec(select(ScanRecord)).all()
    by_id = {record.scan_id: record for record in records}
    assert by_id[UUID(payload_a["scan_id"])].org_id == seeded_org.id
    assert by_id[UUID(payload_b["scan_id"])].org_id == other_org.id


@pytest.mark.parametrize(
    "corrupt_payload",
    [
        lambda payload: {**payload, "unexpected_field": "nope"},
        lambda payload: {
            **payload,
            "hosts": [{**_host(), "unexpected_field": "nope"}],
        },
        lambda payload: {
            **payload,
            "hosts": [
                {
                    **_host(),
                    "ports": [{**_host()["ports"][0], "unexpected_field": "nope"}],
                }
            ],
        },
        lambda payload: {
            **payload,
            "findings": [{**_finding(), "unexpected_field": "nope"}],
        },
        lambda payload: {k: v for k, v in payload.items() if k != "hosts"},
        lambda payload: {**payload, "hosts": [{**_host(), "ip": "2001:db8::1"}]},
        lambda payload: {**payload, "findings": [{**_finding(), "ip": "2001:db8::1"}]},
    ],
)
def test_invalid_payload_refused_422(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    corrupt_payload,
) -> None:
    private_key, _ = agent_keypair
    payload = corrupt_payload(_payload(uuid4()))

    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 422
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_acknowledgement_shape(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    scan_id = uuid4()
    payload = _payload(scan_id, hosts=[_host("10.0.0.7"), _host("10.0.0.8")])

    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 202
    body = response.json()
    assert body == {
        "message": "scan received successfully",
        "scan_id": str(scan_id),
        "hosts_received": 2,
        "status": "accepted",
    }


def test_unsigned_invalid_payload_is_401_not_422(
    client: TestClient,
    administrative_session: Session,
) -> None:
    payload = {**_payload(uuid4()), "unexpected_field": "nope"}
    body = _body(payload)

    response = client.post(PATH, content=body)

    assert response.status_code == 401
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_malformed_json_body_refused_422(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    body = b"{not-json"
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=body
    )

    response = client.post(PATH, headers=headers, content=body)

    assert response.status_code == 422
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_repeated_submission_accepted_no_duplicate_writes(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    scan_id = uuid4()
    payload = _payload(scan_id, hosts=[_host()], findings=[_finding()])

    first = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )
    assert first.status_code == 202
    hosts_after_first = administrative_session.exec(select(ScanHostRecord)).all()
    findings_after_first = administrative_session.exec(select(FindingRecord)).all()
    jobs_after_first = administrative_session.exec(select(EnrichmentJobRecord)).all()

    second = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )
    assert second.status_code == 202
    assert second.json() == first.json()
    assert (
        administrative_session.exec(select(ScanHostRecord)).all() == hosts_after_first
    )
    assert (
        administrative_session.exec(select(FindingRecord)).all()
        == findings_after_first
    )
    assert (
        administrative_session.exec(select(EnrichmentJobRecord)).all()
        == jobs_after_first
    )


def test_repeat_is_not_replay(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _ = agent_keypair
    scan_id = uuid4()
    payload = _payload(scan_id)
    body = _body(payload)
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=body
    )

    first = client.post(PATH, headers=headers, content=body)
    replay = client.post(PATH, headers=headers, content=body)

    assert first.status_code == 202
    assert replay.status_code == 401


def test_late_results_after_write_off_refused_400_and_nothing_written(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
) -> None:
    private_key, _ = agent_keypair
    now = utc_now()
    scan_id = uuid4()
    command = _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    provisioned_agent.last_seen_at = (now - timedelta(minutes=20)).replace(tzinfo=None)
    provisioned_agent.connected_at = None
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    swept = commands.sweep_stale_commands(
        administrative_session, now=now, grace_seconds=900
    )
    assert swept == 1
    administrative_session.refresh(command)
    assert command.status == "failed"

    payload = _payload(scan_id, hosts=[_host()], findings=[_finding()])
    response = _post(
        client, private_key=private_key, device_id=provisioned_agent.id, payload=payload
    )

    assert response.status_code == 400
    administrative_session.refresh(command)
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert command.status == "failed"
    assert scan_record.status == "failed"
    assert (
        administrative_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )
    assert (
        administrative_session.exec(
            select(FindingRecord).where(FindingRecord.scan_id == scan_id)
        ).first()
        is None
    )
    assert (
        administrative_session.exec(
            select(EnrichmentJobRecord).where(
                EnrichmentJobRecord.scan_id == scan_id
            )
        ).first()
        is None
    )


@pytest.mark.parametrize("terminal_status", ["done", "failed", "expired"])
def test_upload_after_done_failed_or_expired_command_is_refused_400(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    seeded_org: Org,
    terminal_status: str,
) -> None:
    private_key, _ = agent_keypair
    now = utc_now()
    scan_id = uuid4()
    command = _seed_placeholder(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan_id,
        now=now,
    )
    command.status = terminal_status
    if terminal_status == "failed":
        command.error_code = "device_offline"
    if terminal_status in {"done", "failed"}:
        command.completed_at = now
    administrative_session.add(command)
    administrative_session.commit()

    response = _post(
        client,
        private_key=private_key,
        device_id=provisioned_agent.id,
        payload=_payload(scan_id, hosts=[_host()], findings=[_finding()]),
    )

    assert response.status_code == 400
    administrative_session.refresh(command)
    scan_record = administrative_session.get(ScanRecord, scan_id)
    assert command.status == terminal_status
    assert scan_record.status == "pending"
    assert (
        administrative_session.exec(
            select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_id)
        ).first()
        is None
    )
