"""Industrial / Modbus ingest models shared by scan ingest."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, constr

MAX_DEVICE_STRING_CHARS = 128
MAX_IDENTIFICATION_OBJECTS = 16
MAX_IDENTIFICATION_SOURCES = 8
MAX_ADDRESS_RANGES_PER_UNIT = 32

DeviceString = Annotated[str | None, Field(max_length=MAX_DEVICE_STRING_CHARS)]
ValueDigest = Annotated[
    str | None,
    Field(pattern=r"^hmac-sha256:[0-9a-f]{64}$"),
]


class ModbusDeviceIdentificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: DeviceString = None
    product_code: DeviceString = None
    major_minor_revision: DeviceString = None
    vendor_url: DeviceString = None
    product_name: DeviceString = None
    model_name: DeviceString = None
    user_application_name: DeviceString = None
    objects: dict[str, str] = Field(
        default_factory=dict, max_length=MAX_IDENTIFICATION_OBJECTS
    )
    truncated: bool = False


class ModbusAddressRangePayload(BaseModel):
    # Older NSPi agents emitted additional read summaries (for example
    # ``value_sha256`` and ``nonzero_count``). They are not required for the
    # current UI, but must not cause the complete industrial observation to be
    # discarded during ingest.
    model_config = ConfigDict(extra="ignore")

    address_space: Literal[
        "coil", "discrete_input", "holding_register", "input_register"
    ]
    start_address: Annotated[int, Field(ge=0, le=65535)]
    count: Annotated[int, Field(ge=1, le=65536)]
    status: Literal[
        "readable",
        "illegal_address",
        "illegal_function",
        "timeout",
        "error",
        "skipped",
    ]
    exception_code: Annotated[int | None, Field(default=None, ge=1, le=255)]
    label: DeviceString = None
    value_digest: ValueDigest = None
    observed_at: datetime


class ModbusUnitPayload(BaseModel):
    # Older agents included optional validation metadata on Modbus units.
    # Keep ingest backwards-compatible while retaining the typed fields used
    # by the current API and persistence layer.
    model_config = ConfigDict(extra="ignore")

    unit_id: Annotated[int, Field(ge=0, le=255)]
    status: Literal["responding", "exception", "timeout", "error", "skipped"]
    exception_code: Annotated[int | None, Field(default=None, ge=1, le=255)]
    error: DeviceString = None
    device_identification: ModbusDeviceIdentificationPayload | None = None
    identification_sources: list[constr(min_length=1)] = Field(
        default_factory=list, max_length=MAX_IDENTIFICATION_SOURCES
    )
    address_ranges: list[ModbusAddressRangePayload] = Field(
        default_factory=list, max_length=MAX_ADDRESS_RANGES_PER_UNIT
    )


class ModbusTcpServicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["modbus_tcp"] = "modbus_tcp"
    port: Annotated[int, Field(ge=1, le=65535)]
    confidence: Literal["suspected", "confirmed"]
    evidence_sources: list[constr(min_length=1)] = Field(default_factory=list)
    mapping_source: str | None = None
    write_requests_sent: Annotated[int, Field(default=0, ge=0)]
    units: list[ModbusUnitPayload] = Field(default_factory=list)
