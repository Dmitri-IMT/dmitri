from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from time import sleep as default_sleep
from typing import Any

from pymodbus.client import ModbusTcpClient

from agent.ot.modbus.client import (
    ModbusClientController,
    ModbusReadResult,
    ModbusReadSession,
)
from agent.ot.modbus.models import ModbusAddressRange, ModbusService
from agent.ot.policy import (
    GENERIC_BASELINE_RANGES,
    MappingProfile,
    MappingRangeRule,
    OtAutomationPolicy,
    selector_matches,
)
from agent.scanner.models import HostInfo


@dataclass(frozen=True, slots=True)
class MappingPlan:
    source: str
    unit_ids: tuple[int, ...]
    ranges: tuple[MappingRangeRule, ...]


@dataclass(slots=True)
class MappingBudget:
    maximum: int
    used: int = 0

    def available(self) -> bool:
        return self.used < self.maximum


@dataclass(slots=True)
class _Observation:
    address_space: str
    start_address: int
    count: int
    status: str
    observed_at: datetime
    capture_values: str
    values: list[int | bool] | None = None
    exception_code: int | None = None
    label: str | None = None


SessionFactory = Callable[..., Any]


def resolve_mapping_plan(
    host: HostInfo,
    service: ModbusService,
    policy: OtAutomationPolicy,
) -> MappingPlan:
    """Choose site, vendor/product, or fixed generic baseline deterministically."""

    discovered_ids = tuple(
        unit.unit_id
        for unit in sorted(service.units, key=lambda item: item.unit_id)
        if 1 <= unit.unit_id <= 247 and unit.status in {"responding", "exception"}
    )[:4]
    vendors, products = _fingerprint_values(service)
    matching = [
        profile
        for profile in policy.mapping_profiles
        if selector_matches(
            profile.selector,
            ip=host.ip,
            mac=host.mac,
            vendors=vendors,
            products=products,
        )
    ]
    site_profiles = [
        profile
        for profile in matching
        if profile.selector.cidrs or profile.selector.macs
    ]
    vendor_profiles = [profile for profile in matching if profile not in site_profiles]
    selected = (site_profiles or vendor_profiles or [None])[0]
    if selected is None:
        return MappingPlan(
            source="generic_baseline",
            unit_ids=discovered_ids,
            ranges=GENERIC_BASELINE_RANGES,
        )
    return MappingPlan(
        source=("site:" if selected in site_profiles else "vendor:") + selected.name,
        unit_ids=_selected_unit_ids(selected, discovered_ids),
        ranges=tuple(selected.ranges),
    )


def map_modbus_service(
    host: HostInfo,
    service: ModbusService,
    *,
    policy: OtAutomationPolicy,
    timeout: float = 1.5,
    cancel_event: threading.Event | None = None,
    controller: ModbusClientController | None = None,
    deadline: float | None = None,
    budget: MappingBudget | None = None,
    session_factory: SessionFactory = ModbusReadSession,
    client_factory: Callable[..., Any] = ModbusTcpClient,
    sleep: Callable[[float], None] = default_sleep,
) -> None:
    """Execute one read-only plan with a single connection and bounded traffic."""

    plan = resolve_mapping_plan(host, service, policy)
    service.mapping_source = plan.source
    if not plan.unit_ids:
        service.mapping_ranges_skipped += len(plan.ranges)
        return
    if budget is None:
        budget = MappingBudget(
            maximum=policy.max_mapping_requests_per_host,
            used=service.requests_sent,
        )
    unit_index = {unit.unit_id: unit for unit in service.units}
    observations: dict[int, list[_Observation]] = {
        unit_id: [] for unit_id in plan.unit_ids
    }
    with session_factory(
        host.ip,
        service.port,
        timeout=timeout,
        controller=controller,
        client_factory=client_factory,
    ) as session:
        for unit_id in plan.unit_ids:
            for rule in plan.ranges:
                if _must_stop(cancel_event, deadline) or not budget.available():
                    service.mapping_ranges_skipped += 1
                    continue
                for start_address, count in _chunks(rule):
                    if _must_stop(cancel_event, deadline) or not budget.available():
                        service.mapping_ranges_skipped += 1
                        break
                    observations[unit_id].extend(
                        _read_chunk(
                            session,
                            unit_id=unit_id,
                            rule=rule,
                            start_address=start_address,
                            count=count,
                            policy=policy,
                            budget=budget,
                            service=service,
                            cancel_event=cancel_event,
                            deadline=deadline,
                            sleep=sleep,
                        )
                    )
    for unit_id, found in observations.items():
        unit_index[unit_id].address_ranges.extend(
            _materialise(item) for item in _merge_adjacent(found)
        )


def _read_chunk(
    session: Any,
    *,
    unit_id: int,
    rule: MappingRangeRule,
    start_address: int,
    count: int,
    policy: OtAutomationPolicy,
    budget: MappingBudget,
    service: ModbusService,
    cancel_event: threading.Event | None,
    deadline: float | None,
    sleep: Callable[[float], None],
) -> list[_Observation]:
    if _must_stop(cancel_event, deadline) or not budget.available():
        service.mapping_ranges_skipped += 1
        return []
    sleep(policy.inter_request_delay_ms / 1000)
    if _must_stop(cancel_event, deadline):
        service.mapping_ranges_skipped += 1
        return []
    result: ModbusReadResult = session.read(
        rule.address_space,
        start_address,
        count,
        unit_id,
    )
    if result.request_sent:
        budget.used += 1
        service.requests_sent += 1
        service.mapping_requests_sent += 1
        if result.status == "timeout":
            service.timeouts += 1
    if (
        result.status == "illegal_address"
        and rule.bisect_on_illegal_address
        and count > rule.minimum_block_size
        and budget.available()
    ):
        left_count = count // 2
        right_count = count - left_count
        return _read_chunk(
            session,
            unit_id=unit_id,
            rule=rule,
            start_address=start_address,
            count=left_count,
            policy=policy,
            budget=budget,
            service=service,
            cancel_event=cancel_event,
            deadline=deadline,
            sleep=sleep,
        ) + _read_chunk(
            session,
            unit_id=unit_id,
            rule=rule,
            start_address=start_address + left_count,
            count=right_count,
            policy=policy,
            budget=budget,
            service=service,
            cancel_event=cancel_event,
            deadline=deadline,
            sleep=sleep,
        )
    return [
        _Observation(
            address_space=rule.address_space,
            start_address=start_address,
            count=count,
            status=result.status,
            observed_at=datetime.now(timezone.utc),
            capture_values=rule.capture_values,
            values=result.values,
            exception_code=result.exception_code,
            label=rule.label,
        )
    ]


def _chunks(rule: MappingRangeRule) -> list[tuple[int, int]]:
    chunks = []
    offset = 0
    while offset < rule.count:
        count = min(rule.block_size, rule.count - offset)
        chunks.append((rule.start_address + offset, count))
        offset += count
    return chunks


def _must_stop(
    cancel_event: threading.Event | None,
    deadline: float | None,
) -> bool:
    return bool(
        (cancel_event is not None and cancel_event.is_set())
        or (deadline is not None and perf_counter() >= deadline)
    )


def _merge_adjacent(items: list[_Observation]) -> list[_Observation]:
    merged: list[_Observation] = []
    for item in items:
        previous = merged[-1] if merged else None
        if previous is not None and _can_merge(previous, item):
            previous.count += item.count
            if previous.values is not None and item.values is not None:
                previous.values.extend(item.values)
            continue
        merged.append(item)
    return merged


def _can_merge(left: _Observation, right: _Observation) -> bool:
    return (
        left.start_address + left.count == right.start_address
        and left.address_space == right.address_space
        and left.status == right.status
        and left.exception_code == right.exception_code
        and left.capture_values == right.capture_values
        and left.label == right.label
        and ((left.values is None) == (right.values is None))
    )


def _materialise(item: _Observation) -> ModbusAddressRange:
    values = item.values if item.status == "readable" else None
    capture = item.capture_values
    numeric = (
        [int(value) for value in values]
        if values is not None and capture != "none"
        else None
    )
    return ModbusAddressRange(
        address_space=item.address_space,  # type: ignore[arg-type]
        start_address=item.start_address,
        count=item.count,
        status=item.status,  # type: ignore[arg-type]
        observed_at=item.observed_at,
        exception_code=item.exception_code,
        label=item.label,
        nonzero_count=(
            sum(value != 0 for value in numeric) if numeric is not None else None
        ),
        value_min=min(numeric) if numeric else (0 if numeric == [] else None),
        value_max=max(numeric) if numeric else (0 if numeric == [] else None),
        values=(list(values) if values is not None and capture == "raw" else None),
        value_sha256=(
            _hash_values(values)
            if values is not None and capture in {"summary", "raw"}
            else None
        ),
    )


def _hash_values(values: list[int | bool]) -> str:
    canonical = json.dumps(values, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _fingerprint_values(service: ModbusService) -> tuple[set[str], set[str]]:
    vendors: set[str] = set()
    products: set[str] = set()
    for unit in service.units:
        identification = unit.device_identification
        if identification is None:
            continue
        if identification.vendor_name:
            vendors.add(_normalise(identification.vendor_name))
        for value in (
            identification.product_code,
            identification.product_name,
            identification.model_name,
        ):
            if value:
                products.add(_normalise(value))
    return vendors, products


def _selected_unit_ids(
    profile: MappingProfile,
    discovered_ids: tuple[int, ...],
) -> tuple[int, ...]:
    if profile.unit_ids is None:
        return discovered_ids
    approved = set(profile.unit_ids)
    return tuple(unit_id for unit_id in discovered_ids if unit_id in approved)


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())
