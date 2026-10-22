from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.core.config import get_settings
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import (
    HostRecord,
    IndustrialServiceRecord,
    ModbusUnitRecord,
    ScanHostRecord,
)
from api.schemas.scan import FindingPayload, HostPayload, PortPayload, ScanIngestRequest
from api.services import read
from api.services.industrial import persist_industrial_services
from api.services.persistence import finding_dedupe_key, persist_scan
from pydantic import ValidationError
from sqlmodel import Session, select

SAMPLE_DIGEST = "hmac-sha256:" + ("a" * 64)


def _industrial_service(port: int = 502) -> dict:
    return {
        "protocol": "modbus_tcp",
        "port": port,
        "confidence": "confirmed",
        "evidence_sources": ["tcp-port", "modbus-discover"],
        "mapping_source": "generic_baseline",
        "write_requests_sent": 0,
        "units": [
            {
                "unit_id": 1,
                "status": "responding",
                "device_identification": {
                    "vendor_name": "Schneider Electric",
                    "product_name": "Modicon M580",
                    "objects": {"0": "Schneider Electric"},
                    "truncated": False,
                },
                "identification_sources": ["modbus-discover", "fc43"],
                "address_ranges": [
                    {
                        "address_space": "coil",
                        "start_address": 0,
                        "count": 4,
                        "status": "readable",
                        "label": "generic baseline sample",
                        "observed_at": "2026-09-12T14:03:11Z",
                        "value_digest": SAMPLE_DIGEST,
                    }
                ],
            },
            {
                "unit_id": 2,
                "status": "responding",
                "device_identification": {
                    "vendor_name": "Siemens",
                    "product_name": "S7-1200",
                    "truncated": False,
                },
                "identification_sources": ["modbus-discover"],
                "address_ranges": [],
            },
        ],
    }


def _opcua_service(port: int = 4840) -> dict:
    return {
        "protocol": "opcua_tcp",
        "port": port,
        "confidence": "confirmed",
        "evidence_sources": ["opcua_get_endpoints"],
        "write_requests_sent": 0,
        "observation": {
            "schema_version": 1,
            "inventory_phase": {
                "status": "completed",
                "reason_codes": [],
                "truncated": False,
                "observed_at": "2026-09-12T14:03:11Z",
            },
            "identity": {"application_name": "Plant OPC UA"},
            "certificate_sha256": None,
            "endpoints": [],
            "mapping": {
                "phase": {
                    "status": "timed_out",
                    "reason_codes": ["timeout"],
                    "truncated": True,
                    "observed_at": "2026-09-12T14:03:11Z",
                },
                "nodes": [],
                "references": [],
                "references_observed": 0,
                "value_reads_attempted": 0,
                "selected_endpoint_index": None,
                "anonymous_session_activated": None,
                "browse_succeeded": None,
                "application_value_read_succeeded": None,
                "value_good_count": 0,
                "security_mode": {
                    "value": "SignAndEncrypt",
                    "source": "get_endpoints",
                    "status": "Good",
                },
                "security_policy": {
                    "value": "http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256",
                    "source": "get_endpoints",
                    "status": "Good",
                },
            },
        },
    }


def _host(ip: str = "192.168.1.50", mac: str = "00:80:F4:11:22:33") -> HostPayload:
    return HostPayload(
        ip=ip,
        mac=mac,
        hostname="plc-line-2.plant.local",
        vendor="Schneider Electric",
        ports=[
            PortPayload(
                port=502,
                protocol="tcp",
                state="open",
                service="mbap",
                version=None,
                cpes=[],
            )
        ],
        industrial_services=[_industrial_service()],
    )


def _scan(hosts: list[HostPayload], findings: list[FindingPayload] | None = None):
    return ScanIngestRequest(
        scan_id=uuid4(),
        timestamp=datetime(2026, 9, 12, 14, 0, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="nspi",
        hosts=hosts,
        findings=findings or [],
    )


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


def test_retention_days_configured() -> None:
    settings = get_settings()
    assert settings.industrial_observation_retention_days == 180


def test_legacy_protocol_omission_is_limited_to_modbus_shape() -> None:
    legacy = _host().model_dump(mode="python")
    service = _industrial_service()
    service.pop("protocol")
    legacy["industrial_services"] = [service]
    parsed = HostPayload.model_validate(legacy)
    assert parsed.industrial_services[0].protocol == "modbus_tcp"

    defaulted_legacy = _host().model_dump(mode="python")
    defaulted_legacy["industrial_services"] = [
        {"port": 502, "confidence": "confirmed"}
    ]
    parsed_defaulted = HostPayload.model_validate(defaulted_legacy)
    assert parsed_defaulted.industrial_services[0].protocol == "modbus_tcp"
    assert parsed_defaulted.industrial_services[0].units == []

    untagged_opcua = _host().model_dump(mode="python")
    untagged_opcua["industrial_services"] = [_opcua_service()]
    untagged_opcua["industrial_services"][0].pop("protocol")
    with pytest.raises(ValidationError):
        HostPayload.model_validate(untagged_opcua)


def test_opcua_schema_rejects_unknown_values_and_excess_endpoints() -> None:
    service = _opcua_service()
    service["observation"]["endpoints"] = [_endpoint() for _ in range(17)]
    with pytest.raises(ValidationError):
        HostPayload.model_validate(
            {
                **_host().model_dump(mode="python"),
                "industrial_services": [service],
            }
        )
    service["observation"]["endpoints"] = [_endpoint()]
    service["observation"]["endpoints"][0]["security_mode"] = "Mixed"
    with pytest.raises(ValidationError):
        HostPayload.model_validate(
            {
                **_host().model_dump(mode="python"),
                "industrial_services": [service],
            }
        )


def _endpoint() -> dict:
    return {
        "endpoint_url": "opc.tcp://192.168.1.50:4840/",
        "security_policy_uri": "http://opcfoundation.org/UA/SecurityPolicy#None",
        "security_mode": "None",
        "transport_profile_uri": "http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary",
        "security_level": 0,
        "user_token_count": 1,
        "user_token_types": ["Anonymous"],
        "target_matches": True,
    }


def test_industrial_observation_lifecycle_fields(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    scan = _scan([_host()])
    _persist(runtime_session, scan, seeded_org, provisioned_agent)

    scan_host = runtime_session.exec(select(ScanHostRecord)).one()
    service = runtime_session.exec(select(IndustrialServiceRecord)).one()
    units = runtime_session.exec(
        select(ModbusUnitRecord).order_by(ModbusUnitRecord.unit_id)
    ).all()

    assert service.scan_host_id == scan_host.id
    assert service.protocol == "modbus_tcp"
    assert service.port == 502
    assert service.confidence == "confirmed"
    assert service.mapping_source == "generic_baseline"
    assert service.evidence_sources_json == ["tcp-port", "modbus-discover"]
    assert service.write_requests_sent == 0
    assert len(units) == 2

    unit_one = units[0]
    assert unit_one.unit_id == 1
    assert unit_one.status == "responding"
    assert unit_one.identification_json["product_name"] == "Modicon M580"
    assert unit_one.identification_sources_json == ["modbus-discover", "fc43"]
    assert unit_one.address_ranges_json[0]["status"] == "readable"
    assert unit_one.address_ranges_json[0]["value_digest"].startswith("hmac-sha256:")

    unit_two = units[1]
    assert unit_two.identification_json["product_name"] == "S7-1200"
    assert unit_two.address_ranges_json == []


def test_persist_industrial_services_is_idempotent(
    runtime_session: Session, seeded_org: Org, provisioned_agent: Agent
) -> None:
    scan = _scan([_host()])
    _persist(runtime_session, scan, seeded_org, provisioned_agent)

    scan_host = runtime_session.exec(select(ScanHostRecord)).one()
    port_index = {}
    for port in scan.hosts[0].ports:
        from api.models.persistence import PortRecord

        port_record = runtime_session.exec(
            select(PortRecord).where(
                PortRecord.scan_host_id == scan_host.id,
                PortRecord.port == port.port,
                PortRecord.protocol == port.protocol,
            )
        ).one()
        port_index[(port.port, port.protocol)] = port_record

    persist_industrial_services(
        runtime_session,
        scan_host.id,
        scan.hosts[0].industrial_services,
        port_index=port_index,
    )
    persist_industrial_services(
        runtime_session,
        scan_host.id,
        scan.hosts[0].industrial_services,
        port_index=port_index,
    )

    services = runtime_session.exec(select(IndustrialServiceRecord)).all()
    units = runtime_session.exec(select(ModbusUnitRecord)).all()
    assert len(services) == 1
    assert len(units) == 2


def test_opcua_and_modbus_persist_and_read_idempotently(
    client,
    runtime_session: Session,
    bearer_headers,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    host = _host()
    payload = host.model_dump(mode="python")
    payload["ports"].append(
        PortPayload(
            port=4840,
            protocol="tcp",
            state="open",
            service="opcua",
            version=None,
            cpes=[],
        )
    )
    payload["industrial_services"].append(_opcua_service())
    host = HostPayload.model_validate(payload)
    scan = _scan([host])
    _persist(runtime_session, scan, seeded_org, provisioned_agent)
    scan_host = runtime_session.exec(select(ScanHostRecord)).one()

    assert len(runtime_session.exec(select(IndustrialServiceRecord)).all()) == 2
    assert len(runtime_session.exec(select(ModbusUnitRecord)).all()) == 2
    ua_row = runtime_session.exec(
        select(IndustrialServiceRecord).where(
            IndustrialServiceRecord.protocol == "opcua_tcp"
        )
    ).one()
    assert ua_row.opcua_observation_json["schema_version"] == 1
    stored_mapping = ua_row.opcua_observation_json["mapping"]
    assert stored_mapping["selected_endpoint_index"] is None
    assert stored_mapping["anonymous_session_activated"] is None
    assert stored_mapping["browse_succeeded"] is None
    assert stored_mapping["application_value_read_succeeded"] is None
    assert ua_row.mapping_source is None
    ua_id = ua_row.id

    from api.models.persistence import PortRecord

    port_index = {
        (port.port, port.protocol): port
        for port in runtime_session.exec(
            select(PortRecord).where(PortRecord.scan_host_id == scan_host.id)
        ).all()
    }
    persist_industrial_services(
        runtime_session,
        scan_host.id,
        scan.hosts[0].industrial_services,
        port_index=port_index,
    )
    assert len(runtime_session.exec(select(IndustrialServiceRecord)).all()) == 2
    assert len(runtime_session.exec(select(ModbusUnitRecord)).all()) == 2

    updated_services = list(scan.hosts[0].industrial_services)
    updated_ua = updated_services[1].model_copy(deep=True)
    updated_ua.observation.identity.application_name = "Updated UA"
    updated_services[1] = updated_ua
    persist_industrial_services(
        runtime_session,
        scan_host.id,
        updated_services,
        port_index=port_index,
    )
    runtime_session.commit()
    runtime_session.refresh(ua_row)
    assert ua_row.id == ua_id
    assert ua_row.opcua_observation_json["identity"]["application_name"] == "Updated UA"
    assert ua_row.opcua_observation_json["mapping"] == stored_mapping
    assert len(runtime_session.exec(select(IndustrialServiceRecord)).all()) == 2
    assert len(runtime_session.exec(select(ModbusUnitRecord)).all()) == 2

    headers = bearer_headers(seeded_org.id, "viewer")
    detail = client.get(f"/api/v1/scans/{scan.scan_id}", headers=headers).json()
    services = detail["hosts"][0]["industrial_services"]
    ua = next(service for service in services if service["protocol"] == "opcua_tcp")
    assert ua["observation"]["schema_version"] == 1
    assert ua["observation"]["identity"]["application_name"] == "Updated UA"
    assert ua["observation"]["mapping"] == stored_mapping
    assert "units" not in ua
    assert detail["hosts"][0]["unreadable_fields"] == []
    host_record = runtime_session.exec(select(HostRecord)).one()
    host_detail = client.get(
        f"/api/v1/hosts/{host_record.id}", headers=headers
    ).json()
    host_ua = next(
        service
        for service in host_detail["industrial_services"]
        if service["protocol"] == "opcua_tcp"
    )
    assert host_ua["observation"]["schema_version"] == 1
    assert host_ua["observation"]["identity"]["application_name"] == "Updated UA"
    assert host_ua["observation"]["mapping"] == stored_mapping


def test_corrupt_opcua_json_degrades_only_ua_observation(
    client,
    runtime_session: Session,
    bearer_headers,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    host = _host()
    payload = host.model_dump(mode="python")
    payload["industrial_services"].append(_opcua_service())
    host = HostPayload.model_validate(payload)
    scan = _scan([host])
    _persist(runtime_session, scan, seeded_org, provisioned_agent)
    ua_row = runtime_session.exec(
        select(IndustrialServiceRecord).where(
            IndustrialServiceRecord.protocol == "opcua_tcp"
        )
    ).one()
    ua_row.opcua_observation_json = {"schema_version": 1, "unexpected": True}
    runtime_session.add(ua_row)
    runtime_session.commit()

    headers = bearer_headers(seeded_org.id, "viewer")
    detail = client.get(f"/api/v1/scans/{scan.scan_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    services = body["hosts"][0]["industrial_services"]
    ua = next(service for service in services if service["protocol"] == "opcua_tcp")
    modbus = next(
        service for service in services if service["protocol"] == "modbus_tcp"
    )
    assert ua["observation"] is None
    assert "opcua_observation" in body["hosts"][0]["unreadable_fields"]
    assert [unit["unit_id"] for unit in modbus["units"]] == [1, 2]

    host_record = runtime_session.exec(select(HostRecord)).one()
    host_detail = client.get(
        f"/api/v1/hosts/{host_record.id}",
        headers=bearer_headers(seeded_org.id, "viewer"),
    ).json()
    host_ua = next(
        service
        for service in host_detail["industrial_services"]
        if service["protocol"] == "opcua_tcp"
    )
    assert host_ua["observation"] is None
    assert "opcua_observation" in host_detail["unreadable_fields"]


def test_finding_read_includes_modbus_unit_attribution(
    runtime_session: Session,
    administrative_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    finding = FindingPayload(
        ip="192.168.1.50",
        port=502,
        protocol="tcp",
        service="mbap",
        severity="high",
        title="Outdated firmware on unit 2",
        description="Firmware on the Siemens unit is behind vendor guidance.",
        recommendation="Schedule maintenance on the affected PLC.",
        evidence="Product S7-1200 reports an old revision.",
        unit_id=2,
    )
    scan = _scan([_host()], findings=[finding])
    _persist(runtime_session, scan, seeded_org, provisioned_agent)

    result = read.list_findings(administrative_session, org_id=seeded_org.id)
    assert result.total == 1
    read_finding = result.data[0]
    assert read_finding.modbus_unit is not None
    assert read_finding.modbus_unit.unit_id == 2
    assert read_finding.modbus_unit.port == 502


def test_finding_dedupe_key_uses_na_placeholder_without_unit_id() -> None:
    without_unit = finding_dedupe_key(
        ip="192.168.1.50",
        port=502,
        protocol="tcp",
        cve_id=None,
        title="Unauthenticated Modbus data read is reachable",
    )
    with_unit = finding_dedupe_key(
        ip="192.168.1.50",
        port=502,
        protocol="tcp",
        cve_id=None,
        title="Unauthenticated Modbus data read is reachable",
        unit_id=2,
    )
    assert without_unit.endswith("|na|unauthenticated modbus data read is reachable")
    assert with_unit.endswith("|2|unauthenticated modbus data read is reachable")
    assert without_unit != with_unit
