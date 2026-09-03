from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class ModbusDeviceIdentification:
    vendor_name: str | None = None
    product_code: str | None = None
    major_minor_revision: str | None = None
    vendor_url: str | None = None
    product_name: str | None = None
    model_name: str | None = None
    user_application_name: str | None = None
    objects: dict[str, str] = field(default_factory=dict)

    @property
    def has_structured_fields(self) -> bool:
        return any(
            (
                self.vendor_name,
                self.product_code,
                self.major_minor_revision,
                self.vendor_url,
                self.product_name,
                self.model_name,
                self.user_application_name,
            )
        )


@dataclass(slots=True)
class ModbusUnit:
    unit_id: int
    status: Literal["responding", "exception", "timeout", "error", "skipped"]
    exception_code: int | None = None
    error: str | None = None
    device_identification: ModbusDeviceIdentification | None = None
    identification_sources: list[str] = field(default_factory=list)
    address_ranges: list[ModbusAddressRange] = field(default_factory=list)
    validations: list[ModbusValidation] = field(default_factory=list)


@dataclass(slots=True)
class ModbusAddressRange:
    address_space: Literal[
        "coil", "discrete_input", "holding_register", "input_register"
    ]
    start_address: int
    count: int
    status: Literal[
        "readable",
        "illegal_address",
        "illegal_function",
        "timeout",
        "error",
        "skipped",
    ]
    observed_at: datetime
    exception_code: int | None = None
    label: str | None = None
    nonzero_count: int | None = None
    value_min: int | None = None
    value_max: int | None = None
    values: list[int | bool] | None = None
    value_sha256: str | None = None


@dataclass(slots=True)
class ModbusValidation:
    address_space: Literal["coil", "holding_register"]
    address: int
    label: str
    function_code: Literal[5, 6]
    expected_current_value: int | bool
    test_value: int | bool
    write_status: Literal["accepted", "rejected", "timeout", "error", "skipped"]
    restoration_status: Literal["not_required", "verified", "unverified", "failed"]
    change_ticket: str
    started_at: datetime
    completed_at: datetime
    original_value: int | bool | None = None
    read_back_value: int | bool | None = None
    final_value: int | bool | None = None


@dataclass(slots=True)
class ModbusService:
    port: int
    confidence: Literal["suspected", "confirmed"]
    evidence_sources: list[str] = field(default_factory=list)
    units: list[ModbusUnit] = field(default_factory=list)
    requests_sent: int = 0
    timeouts: int = 0
    mapping_source: str | None = None
    mapping_requests_sent: int = 0
    mapping_ranges_skipped: int = 0
