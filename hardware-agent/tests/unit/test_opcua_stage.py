from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from agent.config import AgentSettings
from agent.normalize.contracts import ScanPayload
from agent.ot.modbus.models import ModbusService
from agent.ot.opcua.models import (
    OpcUaInventory,
    OpcUaInventoryEndpoint,
    OpcUaMappingResult,
)
from agent.ot.policy import OtAutomationPolicy
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo, StageCoverage
from agent.scanner.stages import (
    build_host_payload,
    build_metadata,
    run_ot_inspection_stage,
)


def _ua_service(port: int = 4840) -> OpcUaInventory:
    return OpcUaInventory(
        protocol="opcua_tcp",
        port=port,
        confidence="confirmed",
        evidence_sources=("opcua_get_endpoints",),
        inventory_status="completed",
        observed_at=datetime.now(timezone.utc),
        endpoints=(
            OpcUaInventoryEndpoint(
                endpoint_url=f"opc.tcp://192.168.1.20:{port}/ua",
                security_policy_uri="http://opcfoundation.org/UA/SecurityPolicy#None",
                security_mode="None",
                transport_profile_uri=(
                    "http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary"
                ),
                security_level=0,
                user_token_count=1,
                target_matches=True,
                user_token_types=("Anonymous",),
            ),
        ),
    )


class _Reporter:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


class _Runner:
    nmap_path = "nmap"


def test_shared_stage_inventories_before_mapping_and_preserves_both_protocols(
    monkeypatch,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[
            PortInfo(port=502, service=ServiceInfo(name="modbus")),
            PortInfo(port=4840, service=ServiceInfo(name="opcua")),
        ],
    )
    calls: list[str] = []
    modbus = ModbusService(port=502, confidence="confirmed", evidence_sources=["probe"])

    def inventory_modbus(*_args, **_kwargs):
        calls.append("modbus_inventory")
        return [modbus]

    def inventory_ua(*_args, **_kwargs):
        calls.append("opcua_inventory")
        return [_ua_service()]

    def map_modbus(*_args, **_kwargs):
        calls.append("modbus_mapping")

    def map_ua(*_args, **_kwargs):
        calls.append("opcua_mapping")
        return OpcUaMappingResult("completed", browse_succeeded=True)

    monkeypatch.setattr("agent.scanner.stages.inventory_modbus_host", inventory_modbus)
    monkeypatch.setattr("agent.scanner.stages._inventory_opcua_host", inventory_ua)
    monkeypatch.setattr("agent.scanner.stages.map_modbus_service", map_modbus)
    monkeypatch.setattr("agent.scanner.stages._map_opcua_service", map_ua)

    run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi", nspi_submode="read_only_mapping"),
        [host],
    )

    assert calls == [
        "modbus_inventory",
        "opcua_inventory",
        "modbus_mapping",
        "opcua_mapping",
    ]
    assert host.industrial_services == [modbus]
    assert host.opcua_services[0].mapping is not None
    payload = build_host_payload(host)
    assert [service.protocol for service in payload.industrial_services] == [
        "modbus_tcp",
        "opcua_tcp",
    ]


def test_default_inventory_does_not_map_opcua(monkeypatch) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[PortInfo(port=4840, service=ServiceInfo(name="opcua"))],
    )
    monkeypatch.setattr(
        "agent.scanner.stages._inventory_opcua_host",
        lambda *_args, **_kwargs: [_ua_service()],
    )
    monkeypatch.setattr(
        "agent.scanner.stages._map_opcua_service",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("mapping ran")),
    )

    run_ot_inspection_stage(AgentSettings(scan_mode="nspi"), [host])

    assert host.opcua_services
    assert host.opcua_services[0].mapping is None


def test_agent_host_name_matches_only_detected_local_ip() -> None:
    own = HostInfo(ip="192.168.1.20", hostname="router")
    other = HostInfo(ip="192.168.1.21", hostname="router")

    own_payload = build_host_payload(
        own, agent_ip="192.168.1.20", machine_type="unknown"
    )
    other_payload = build_host_payload(other, agent_ip="192.168.1.20")

    assert own_payload.hostname == "DMITRI"
    assert own_payload.machine_type == "unknown"
    assert other_payload.hostname == "router"


def test_runner_payload_accepts_opcua_coverage_for_failed_and_skipped_services(
    monkeypatch,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[PortInfo(port=4840, service=ServiceInfo(name="opcua"))],
    )
    failed = replace(
        _ua_service(),
        confidence="suspected",
        inventory_status="failed",
        reason_code="service_error",
        reason_codes=("service_error",),
    )
    skipped = replace(
        _ua_service(4841),
        confidence="suspected",
        inventory_status="partial",
        reason_code="stage_deadline",
        reason_codes=("stage_deadline",),
    )
    completed = _ua_service(4842)
    host.opcua_services = [failed, skipped, completed]
    host.stage_coverage.extend(
        [
            StageCoverage(
                "ot_inspection", "failed", "opcua_inspection", "service_error"
            ),
            StageCoverage(
                "ot_inspection", "skipped", "opcua_inspection", "stage_budget"
            ),
            StageCoverage("ot_inspection", "completed", "opcua_inspection"),
        ]
    )
    from agent.scanner.runner import ScanRunner
    from agent.utils.network import LocalNetworkInfo

    runner = ScanRunner(subnet="192.168.1.0/24", scan_mode="nspi", runner=_Runner())
    payload = runner._build_payload(
        scan_id=uuid4(),
        settings=AgentSettings(scan_mode="nspi"),
        network_info=LocalNetworkInfo(
            ip="192.168.1.20",
            netmask="255.255.255.0",
            subnet="192.168.1.0/24",
            interface="eth0",
        ),
        runner=_Runner(),
        started_counter=perf_counter(),
        hosts=[host],
        partial_result=False,
        interrupted_stage=None,
        terminated_by="completed",
    )
    assert [unit.evidence_source for unit in payload.coverage] == [
        "opcua_inspection",
        "opcua_inspection",
        "opcua_inspection",
    ]
    assert [unit.outcome for unit in payload.coverage] == [
        "failed",
        "skipped",
        "completed",
    ]
    ScanPayload.model_validate(payload.model_dump(mode="json"))


def test_opcua_payload_serializes_measured_write_counter() -> None:
    service = replace(_ua_service(), write_requests_sent=2)
    host = HostInfo(ip="192.168.1.20", hostname="plc")
    host.opcua_services = [service]
    payload = build_host_payload(host)
    assert payload.industrial_services[0].write_requests_sent == 2


def test_opcua_active_inventory_is_limited_to_four_ports(monkeypatch) -> None:
    from agent.scanner.stages import _inventory_opcua_host

    ports = [
        PortInfo(port=4840 + index, service=ServiceInfo(name="opcua"))
        for index in range(6)
    ] + [PortInfo(port=4845, service=ServiceInfo(name="opcua"))]
    host = HostInfo(ip="192.168.1.20", hostname="plc", ports=ports)
    inspected = []

    async def inventory(_client, _ip, port, **_kwargs):
        inspected.append(port)
        return _ua_service(port)

    monkeypatch.setattr("agent.scanner.stages.inventory_opcua_service", inventory)
    results = _inventory_opcua_host(
        host, cancel_event=None, deadline=None, request_budget=32
    )
    assert inspected == [4840, 4841, 4842, 4843]
    assert len(results) == 6
    assert [item.reason_code for item in results[-2:]] == [
        "service_limit",
        "service_limit",
    ]


def test_dual_protocol_request_budgets_allow_32_each_and_64_total(monkeypatch) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[
            PortInfo(port=502, service=ServiceInfo(name="modbus")),
            PortInfo(port=4840, service=ServiceInfo(name="opcua")),
        ],
    )
    modbus = ModbusService(
        port=502, confidence="confirmed", evidence_sources=["probe"], requests_sent=1
    )
    opcua = replace(_ua_service(), requests_sent=1)
    inventory_budgets = []

    def inventory_modbus(_host, **kwargs):
        inventory_budgets.append(("modbus", kwargs["request_budget"]))
        return [modbus]

    def inventory_ua(_host, **kwargs):
        inventory_budgets.append(("opcua", kwargs["request_budget"]))
        return [opcua]

    def map_modbus(_host, service, *, budget, **_kwargs):
        service.requests_sent += budget.maximum - budget.used
        budget.used = budget.maximum

    def map_ua(_service, _host, *, request_budget, **_kwargs):
        return OpcUaMappingResult(
            "completed", requests_sent=request_budget, browse_succeeded=True
        )

    monkeypatch.setattr("agent.scanner.stages.inventory_modbus_host", inventory_modbus)
    monkeypatch.setattr("agent.scanner.stages._inventory_opcua_host", inventory_ua)
    monkeypatch.setattr("agent.scanner.stages.map_modbus_service", map_modbus)
    monkeypatch.setattr("agent.scanner.stages._map_opcua_service", map_ua)

    run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi", nspi_submode="read_only_mapping"), [host]
    )

    assert inventory_budgets == [("modbus", 32), ("opcua", 32)]
    assert modbus.requests_sent == 32
    opcua_result = host.opcua_services[0]
    assert opcua_result.requests_sent + opcua_result.mapping.requests_sent == 32
    total_requests = (
        modbus.requests_sent
        + opcua_result.requests_sent
        + opcua_result.mapping.requests_sent
    )
    assert total_requests == 64
    metadata = build_metadata(
        runner=_Runner(),
        settings=AgentSettings(scan_mode="nspi", nspi_submode="read_only_mapping"),
        network_info=None,
        elapsed_seconds=1,
        hosts_discovered=1,
        findings_count=0,
        hosts=[host],
    )
    assert metadata["modbus_requests_sent"] == 32
    assert metadata["opcua_requests_sent"] == 32
    assert metadata["industrial_requests_sent"] == 64


def test_shared_stage_enforces_minimum_opcua_pacing_for_inventory_and_mapping(
    monkeypatch,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[PortInfo(port=4840, service=ServiceInfo(name="opcua"))],
    )
    inventory_pacing: list[int] = []
    mapping_pacing: list[int] = []

    def inventory_ua(_host, *, pacing_ms, **_kwargs):
        inventory_pacing.append(pacing_ms)
        return [_ua_service()]

    def map_ua(_service, _host, *, pacing_ms, **_kwargs):
        mapping_pacing.append(pacing_ms)
        return OpcUaMappingResult("completed", browse_succeeded=True)

    monkeypatch.setattr("agent.scanner.stages._inventory_opcua_host", inventory_ua)
    monkeypatch.setattr("agent.scanner.stages._map_opcua_service", map_ua)

    run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi", nspi_submode="read_only_mapping"),
        [host],
        policy=OtAutomationPolicy(inter_request_delay_ms=25),
    )

    assert inventory_pacing == [100]
    assert mapping_pacing == [100]


def test_actual_opcua_mapper_wrapper_passes_policy_pacing_to_fake_transport(
    monkeypatch,
) -> None:
    from agent.ot.opcua.client import OpcUaClient
    from agent.ot.opcua.models import (
        OpcUaClientResult,
        OpcUaEndpoint,
        OpcUaRequestStats,
    )
    from agent.scanner.stages import _map_opcua_service

    calls = []

    async def fake_transport(self, host, port, endpoint, **kwargs):
        calls.append((host, port, endpoint.endpoint_url, kwargs))
        return OpcUaClientResult(
            "ok",
            mapping=OpcUaMappingResult("completed", requests_sent=2),
            stats=OpcUaRequestStats(requests_total=2),
        )

    monkeypatch.setattr(OpcUaClient, "map_anonymous", fake_transport)
    result = _map_opcua_service(
        replace(
            _ua_service(),
            client_endpoints=(
                OpcUaEndpoint(
                    endpoint_url="opc.tcp://192.168.1.20:4840/ua",
                    security_policy_uri="http://opcfoundation.org/UA/SecurityPolicy#None",
                    security_mode="None",
                    transport_profile_uri="uatcp",
                    security_level=0,
                    user_token_count=1,
                    user_token_types=("Anonymous",),
                ),
            ),
        ),
        "192.168.1.20",
        cancel_event=None,
        deadline=None,
        request_budget=8,
        pacing_ms=250,
    )

    assert result.status == "completed"
    assert result.requests_sent == 2
    assert calls[0][3]["pacing_ms"] == 250


def test_stage_records_opcua_coverage_per_service_outcome(monkeypatch) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[
            PortInfo(port=4840 + index, service=ServiceInfo(name="opcua"))
            for index in range(3)
        ],
    )
    services = [
        _ua_service(4840),
        replace(
            _ua_service(4841),
            inventory_status="partial",
            reason_code="request_budget_exhausted",
            reason_codes=("request_budget_exhausted",),
        ),
        replace(
            _ua_service(4842),
            confidence="suspected",
            inventory_status="failed",
            reason_code="service_error",
            reason_codes=("service_error",),
        ),
    ]
    monkeypatch.setattr(
        "agent.scanner.stages._inventory_opcua_host",
        lambda *_args, **_kwargs: services,
    )

    run_ot_inspection_stage(AgentSettings(scan_mode="nspi"), [host])

    assert [
        (item.outcome, item.reason_code, item.port, item.protocol, item.tool)
        for item in host.stage_coverage
    ] == [
        ("completed", None, 4840, "tcp", "opcua"),
        ("partial", "limited_coverage", 4841, "tcp", "opcua"),
        ("failed", "service_error", 4842, "tcp", "opcua"),
    ]
