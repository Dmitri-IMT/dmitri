from __future__ import annotations

import logging
import threading

import pytest
from agent.ot.digest import DIGEST_PREFIX
from agent.ot.modbus.client import ModbusReadResult
from agent.ot.modbus.mapper import map_modbus_service, resolve_mapping_plan
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.ot.policy import MappingProfile, OtAutomationPolicy
from agent.scanner.models import HostInfo, MacIdentity


class _Session:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.calls = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        self.closed = True

    def read(self, address_space, start_address, count, unit_id):
        self.calls.append((address_space, start_address, count, unit_id))
        if self.responses:
            return self.responses.pop(0)
        values = [False] * count if "coil" in address_space else list(range(count))
        return ModbusReadResult(
            status="readable", values=values, request_sent=True
        )


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


def test_unconfigured_policy_resolves_four_range_generic_baseline() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    plan = resolve_mapping_plan(host, _identified_service(), OtAutomationPolicy())

    assert plan.source == "generic_baseline"
    assert plan.unit_ids == (1,)
    assert [item.address_space for item in plan.ranges] == [
        "coil",
        "discrete_input",
        "holding_register",
        "input_register",
    ]
    assert all(item.start_address == 0 and item.count == 4 for item in plan.ranges)


def test_site_profile_wins_over_vendor_profile_and_reuses_discovered_units() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc",
        identity=MacIdentity(mac="00:11:22:33:44:55"),
    )
    vendor = MappingProfile(
        name="vendor",
        selector={"vendors": ["Schneider Electric"]},
        ranges=[{"address_space": "coil", "start_address": 20, "count": 1}],
    )
    site = MappingProfile(
        name="site",
        selector={"cidrs": ["192.168.10.0/24"]},
        ranges=[
            {"address_space": "holding_register", "start_address": 100, "count": 1}
        ],
    )

    plan = resolve_mapping_plan(
        host,
        _identified_service(),
        OtAutomationPolicy(mapping_profiles=[vendor, site]),
    )

    assert plan.source == "site:site"
    assert plan.unit_ids == (1,)
    assert plan.ranges[0].start_address == 100


def test_mapper_calls_all_four_read_functions_and_records_summary() -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    session = _Session()

    map_modbus_service(
        host,
        service,
        policy=OtAutomationPolicy(),
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
    )

    assert session.calls == [
        ("coil", 0, 4, 1),
        ("discrete_input", 0, 4, 1),
        ("holding_register", 0, 4, 1),
        ("input_register", 0, 4, 1),
    ]
    ranges = service.units[0].address_ranges
    assert [item.status for item in ranges] == ["readable"] * 4
    assert ranges[2].value_digest is None
    assert service.mapping_source == "generic_baseline"
    assert service.requests_sent == 4


def test_mapper_never_bisects_a_timeout() -> None:
    service = _identified_service()
    session = _Session(
        [ModbusReadResult(status="timeout", request_sent=True, error="slow")]
    )
    profile = MappingProfile(
        name="lab",
        selector={"cidrs": ["192.168.10.0/24"]},
        ranges=[
            {
                "address_space": "holding_register",
                "start_address": 0,
                "count": 8,
                "block_size": 8,
                "bisect_on_illegal_address": True,
            }
        ],
    )

    map_modbus_service(
        HostInfo(ip="192.168.10.30", hostname="plc"),
        service,
        policy=OtAutomationPolicy(mapping_profiles=[profile]),
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
    )

    assert session.calls == [("holding_register", 0, 8, 1)]
    assert service.units[0].address_ranges[0].status == "timeout"


def test_mapper_bisects_only_illegal_address_within_request_budget() -> None:
    service = _identified_service()
    session = _Session(
        [
            ModbusReadResult(
                status="illegal_address", exception_code=2, request_sent=True
            ),
            ModbusReadResult(status="readable", values=[1, 2], request_sent=True),
            ModbusReadResult(
                status="illegal_address", exception_code=2, request_sent=True
            ),
            ModbusReadResult(status="readable", values=[3], request_sent=True),
            ModbusReadResult(
                status="illegal_address", exception_code=2, request_sent=True
            ),
        ]
    )
    profile = MappingProfile(
        name="lab",
        selector={"cidrs": ["192.168.10.0/24"]},
        ranges=[
            {
                "address_space": "holding_register",
                "start_address": 0,
                "count": 4,
                "block_size": 4,
                "bisect_on_illegal_address": True,
            }
        ],
    )

    map_modbus_service(
        HostInfo(ip="192.168.10.30", hostname="plc"),
        service,
        policy=OtAutomationPolicy(
            mapping_profiles=[profile], max_mapping_requests_per_host=5
        ),
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
    )

    assert len(session.calls) == 5
    ranges = service.units[0].address_ranges
    assert [(item.start_address, item.count, item.status) for item in ranges] == [
        (0, 3, "readable"),
        (3, 1, "illegal_address"),
    ]


def test_cancellation_marks_remaining_ranges_skipped_without_a_request() -> None:
    cancel = threading.Event()
    cancel.set()
    service = _identified_service()
    session = _Session()

    map_modbus_service(
        HostInfo(ip="192.168.10.30", hostname="plc"),
        service,
        policy=OtAutomationPolicy(),
        cancel_event=cancel,
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
    )

    assert session.calls == []
    assert service.units[0].address_ranges == []


def test_capture_none_records_only_range_status() -> None:
    service = _identified_service()
    session = _Session(
        [ModbusReadResult(status="readable", values=[0, 4], request_sent=True)]
    )
    profile = MappingProfile(
        name="status-only",
        selector={"cidrs": ["192.168.10.0/24"]},
        ranges=[
            {
                "address_space": "holding_register",
                "start_address": 20,
                "count": 2,
                "block_size": 2,
                "capture_values": "none",
            }
        ],
    )

    map_modbus_service(
        HostInfo(ip="192.168.10.30", hostname="plc"),
        service,
        policy=OtAutomationPolicy(mapping_profiles=[profile]),
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
    )

    observed = service.units[0].address_ranges[0]
    assert observed.status == "readable"
    assert observed.value_digest is None


def test_empty_numeric_list_does_not_report_min_or_max_zero() -> None:
    service = _identified_service()
    session = _Session(
        [ModbusReadResult(status="readable", values=[], request_sent=True)]
    )
    profile = MappingProfile(
        name="lab",
        selector={"cidrs": ["192.168.10.0/24"]},
        ranges=[
            {
                "address_space": "holding_register",
                "start_address": 0,
                "count": 1,
                "block_size": 1,
            }
        ],
    )

    map_modbus_service(
        HostInfo(ip="192.168.10.30", hostname="plc"),
        service,
        policy=OtAutomationPolicy(mapping_profiles=[profile]),
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
    )

    observed = service.units[0].address_ranges[0]
    assert observed.value_digest is None


def test_mapper_records_keyed_digest_when_key_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = bytes.fromhex("b" * 64)
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    session = _Session()

    map_modbus_service(
        host,
        service,
        policy=OtAutomationPolicy(),
        session_factory=lambda *args, **kwargs: session,
        sleep=lambda _: None,
        digest_key=key,
    )

    digest = service.units[0].address_ranges[2].value_digest
    assert digest is not None
    assert digest.startswith(DIGEST_PREFIX)


def test_mapper_does_not_log_process_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = HostInfo(ip="192.168.10.30", hostname="plc")
    service = _identified_service()
    session = _Session()

    with caplog.at_level(logging.DEBUG):
        map_modbus_service(
            host,
            service,
            policy=OtAutomationPolicy(),
            session_factory=lambda *args, **kwargs: session,
            sleep=lambda _: None,
        )

    for record in caplog.records:
        assert "0, 1, 2, 3" not in record.getMessage()
        assert "[0, 1, 2, 3]" not in record.getMessage()
