from __future__ import annotations

from agent.ot.modbus.client import ModbusReadResult
from agent.ot.modbus.mapper import map_modbus_service, resolve_mapping_plan
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.ot.policy import GENERIC_BASELINE_RANGES, MappingProfile, OtAutomationPolicy
from agent.scanner.models import HostInfo, MacIdentity


def _identified_service() -> ModbusService:
    return ModbusService(
        port=502,
        confidence="confirmed",
        units=[
            ModbusUnit(
                unit_id=1,
                status="responding",
                device_identification=ModbusDeviceIdentification(
                    vendor_name="Schneider Electric",
                    product_code="BMX P34",
                    major_minor_revision="2.60",
                ),
            )
        ],
    )


def test_identity_only_match_cannot_widen_beyond_generic_baseline() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    wide = MappingProfile(
        name="wide-vendor",
        selector={"vendors": ["Schneider Electric"]},
        ranges=[
            {
                "address_space": "coil",
                "start_address": 0,
                "count": 8,
                "block_size": 8,
            }
        ],
    )

    plan = resolve_mapping_plan(
        host,
        service,
        OtAutomationPolicy(mapping_profiles=[wide]),
    )

    assert plan.source == "generic_baseline"
    assert plan.ranges == GENERIC_BASELINE_RANGES
    assert plan.identity_not_corroborated is True
    assert "identity-not-corroborated" not in service.evidence_sources


def test_identity_only_match_cannot_read_outside_baseline_addresses() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    shifted = MappingProfile(
        name="shifted-vendor",
        selector={"vendors": ["Schneider Electric"]},
        ranges=[
            {
                "address_space": "coil",
                "start_address": 4,
                "count": 1,
                "block_size": 1,
            }
        ],
    )

    plan = resolve_mapping_plan(
        host,
        service,
        OtAutomationPolicy(mapping_profiles=[shifted]),
    )

    assert plan.source == "generic_baseline"
    assert plan.ranges == GENERIC_BASELINE_RANGES
    assert plan.identity_not_corroborated is True
    assert "identity-not-corroborated" not in service.evidence_sources


def test_cidr_match_can_widen_beyond_generic_baseline() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    wide = MappingProfile(
        name="wide-site",
        selector={
            "cidrs": ["192.168.10.0/24"],
            "vendors": ["Schneider Electric"],
        },
        ranges=[
            {
                "address_space": "coil",
                "start_address": 0,
                "count": 8,
                "block_size": 8,
            }
        ],
    )

    plan = resolve_mapping_plan(
        host,
        service,
        OtAutomationPolicy(mapping_profiles=[wide]),
    )

    assert plan.source == "site:wide-site"
    assert plan.ranges[0].count == 8
    assert "identity-not-corroborated" not in service.evidence_sources


def test_mac_match_can_widen_beyond_generic_baseline() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc",
        identity=MacIdentity(mac="00:11:22:33:44:55"),
    )
    service = _identified_service()
    wide = MappingProfile(
        name="wide-site",
        selector={
            "macs": ["00:11:22:33:44:55"],
            "vendors": ["Schneider Electric"],
        },
        ranges=[
            {
                "address_space": "coil",
                "start_address": 0,
                "count": 8,
                "block_size": 8,
            }
        ],
    )

    plan = resolve_mapping_plan(
        host,
        service,
        OtAutomationPolicy(mapping_profiles=[wide]),
    )

    assert plan.source == "site:wide-site"
    assert plan.ranges[0].count == 8


def test_narrower_identity_profile_always_applies() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    narrow = MappingProfile(
        name="narrow-vendor",
        selector={"vendors": ["Schneider Electric"]},
        ranges=[
            {
                "address_space": "coil",
                "start_address": 0,
                "count": 1,
                "block_size": 1,
            }
        ],
    )

    plan = resolve_mapping_plan(
        host,
        service,
        OtAutomationPolicy(mapping_profiles=[narrow]),
    )

    assert plan.source == "vendor:narrow-vendor"
    assert plan.ranges[0].count == 1
    assert plan.identity_not_corroborated is False


def test_map_appends_identity_not_corroborated_once() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    wide = MappingProfile(
        name="wide-vendor",
        selector={"vendors": ["Schneider Electric"]},
        ranges=[
            {
                "address_space": "coil",
                "start_address": 0,
                "count": 8,
                "block_size": 8,
            }
        ],
    )

    map_modbus_service(
        host,
        service,
        policy=OtAutomationPolicy(mapping_profiles=[wide]),
        session_factory=lambda *args, **kwargs: _NoOpSession(),
        sleep=lambda _: None,
    )

    assert service.evidence_sources.count("identity-not-corroborated") == 1


class _NoOpSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args, **kwargs):
        return ModbusReadResult(status="illegal_address", request_sent=True)
