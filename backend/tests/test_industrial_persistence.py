from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from api.core.config import get_settings
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import (
    IndustrialServiceRecord,
    ModbusUnitRecord,
    ScanHostRecord,
)
from api.schemas.scan import FindingPayload, HostPayload, PortPayload, ScanIngestRequest
from api.services import read
from api.services.industrial import persist_industrial_services
from api.services.persistence import persist_scan
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


def _host(ip: str = "192.168.1.50") -> HostPayload:
    return HostPayload(
        ip=ip,
        mac="00:80:F4:11:22:33",
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
