from __future__ import annotations

import json
import os
import platform
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

AddressSpace = Literal["coil", "discrete_input", "holding_register", "input_register"]
CaptureValues = Literal["none", "summary", "raw"]

MAX_MAPPING_RANGES_PER_PROFILE = 16
MAX_MAPPING_RANGE_COUNT = 256
MAX_MAPPING_BLOCK_SIZE = 64
MAX_MAPPING_REQUESTS_PER_HOST = 32
MAX_MAPPING_UNIT_IDS = 4
MAX_OT_STAGE_SECONDS = 600
MAX_OT_HOST_SECONDS = 90


def min_not_none(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return min(present)


class OtPolicyError(ValueError):
    pass


class MappingRangeRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    address_space: AddressSpace
    start_address: int = Field(ge=0, le=65535)
    count: int = Field(ge=1, le=MAX_MAPPING_RANGE_COUNT)
    block_size: int = Field(default=8, ge=1, le=MAX_MAPPING_BLOCK_SIZE)
    capture_values: CaptureValues = "summary"
    bisect_on_illegal_address: bool = False
    minimum_block_size: int = Field(default=1, ge=1, le=MAX_MAPPING_BLOCK_SIZE)
    label: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_bounds(self) -> MappingRangeRule:
        if self.start_address + self.count > 65536:
            raise ValueError("mapping range exceeds Modbus address 65535")
        if self.minimum_block_size > self.block_size:
            raise ValueError("minimum_block_size cannot exceed block_size")
        if self.address_space in {"holding_register", "input_register"}:
            if self.block_size > 32:
                raise ValueError("register block_size cannot exceed 32")
        if self.capture_values == "raw" and self.count > 128:
            raise ValueError("raw capture cannot exceed 128 values per range")
        return self


class MappingProfileSelector(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cidrs: list[str] = Field(default_factory=list, max_length=16)
    macs: list[str] = Field(default_factory=list, max_length=16)
    vendors: list[str] = Field(default_factory=list, max_length=16)
    products: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_selector(self) -> MappingProfileSelector:
        if not any((self.cidrs, self.macs, self.vendors, self.products)):
            raise ValueError("a mapping profile selector cannot be empty")
        for cidr in self.cidrs:
            IPv4Network(cidr, strict=False)
        return self


class MappingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=80)
    selector: MappingProfileSelector
    unit_ids: list[int] | None = Field(
        default=None, min_length=1, max_length=MAX_MAPPING_UNIT_IDS
    )
    ranges: list[MappingRangeRule] = Field(
        min_length=1, max_length=MAX_MAPPING_RANGES_PER_PROFILE
    )

    @model_validator(mode="after")
    def validate_unit_ids(self) -> MappingProfile:
        if self.unit_ids is not None:
            if len(set(self.unit_ids)) != len(self.unit_ids):
                raise ValueError("mapping profile unit_ids must be unique")
            if any(unit_id < 1 or unit_id > 247 for unit_id in self.unit_ids):
                raise ValueError("mapping profile unit_ids must be between 1 and 247")
        return self


class OtAutomationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    inter_request_delay_ms: int = Field(default=100, ge=25, le=2000)
    max_mapping_requests_per_host: int = Field(
        default=MAX_MAPPING_REQUESTS_PER_HOST,
        ge=1,
        le=MAX_MAPPING_REQUESTS_PER_HOST,
    )
    mapping_profiles: list[MappingProfile] = Field(default_factory=list, max_length=64)


_CAPTURE_VALUES_ORDER: dict[CaptureValues, int] = {
    "none": 0,
    "summary": 1,
    "raw": 2,
}


def profile_is_conservative(profile: MappingProfile) -> bool:
    """True when the profile is no broader than GENERIC_BASELINE_RANGES."""

    baseline = GENERIC_BASELINE_RANGES
    if len(profile.ranges) > len(baseline):
        return False
    if profile.unit_ids is not None and len(profile.unit_ids) > MAX_MAPPING_UNIT_IDS:
        return False

    baseline_addresses: dict[AddressSpace, int] = {}
    baseline_block_size: dict[AddressSpace, int] = {}
    baseline_capture: dict[AddressSpace, int] = {}
    for rule in baseline:
        baseline_addresses[rule.address_space] = (
            baseline_addresses.get(rule.address_space, 0) + rule.count
        )
        baseline_block_size[rule.address_space] = max(
            baseline_block_size.get(rule.address_space, 0),
            rule.block_size,
        )
        baseline_capture[rule.address_space] = max(
            baseline_capture.get(rule.address_space, 0),
            _CAPTURE_VALUES_ORDER[rule.capture_values],
        )

    profile_addresses: dict[AddressSpace, int] = {}
    profile_block_size: dict[AddressSpace, int] = {}
    profile_capture: dict[AddressSpace, int] = {}
    for rule in profile.ranges:
        profile_addresses[rule.address_space] = (
            profile_addresses.get(rule.address_space, 0) + rule.count
        )
        profile_block_size[rule.address_space] = max(
            profile_block_size.get(rule.address_space, 0),
            rule.block_size,
        )
        profile_capture[rule.address_space] = max(
            profile_capture.get(rule.address_space, 0),
            _CAPTURE_VALUES_ORDER[rule.capture_values],
        )

    for space, count in profile_addresses.items():
        if count > baseline_addresses.get(space, 0):
            return False
        if profile_block_size[space] > baseline_block_size.get(space, 0):
            return False
        if profile_capture[space] > baseline_capture.get(space, 0):
            return False
    return True


GENERIC_BASELINE_RANGES = (
    MappingRangeRule(
        address_space="coil",
        start_address=0,
        count=4,
        block_size=4,
        label="generic baseline sample",
    ),
    MappingRangeRule(
        address_space="discrete_input",
        start_address=0,
        count=4,
        block_size=4,
        label="generic baseline sample",
    ),
    MappingRangeRule(
        address_space="holding_register",
        start_address=0,
        count=4,
        block_size=4,
        label="generic baseline sample",
    ),
    MappingRangeRule(
        address_space="input_register",
        start_address=0,
        count=4,
        block_size=4,
        label="generic baseline sample",
    ),
)


def default_ot_policy_path() -> Path:
    configured = os.environ.get("DMITRI_OT_POLICY_PATH")
    if configured:
        return Path(configured).expanduser()
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(str(PureWindowsPath(base) / "Dmitri" / "ot-policy.json"))
    xdg_config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(xdg_config) / "dmitri" / "ot-policy.json"


def load_ot_policy(path: Path | None = None) -> OtAutomationPolicy:
    policy_path = path or default_ot_policy_path()
    if not policy_path.is_file():
        return OtAutomationPolicy()
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        return OtAutomationPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise OtPolicyError(
            f"Invalid OT automation policy {policy_path}: {exc}"
        ) from exc


def selector_matches(
    selector: MappingProfileSelector,
    *,
    ip: str,
    mac: str | None,
    vendors: set[str],
    products: set[str],
) -> bool:
    if selector.cidrs and not any(
        IPv4Address(ip) in IPv4Network(cidr, strict=False) for cidr in selector.cidrs
    ):
        return False
    if selector.macs and _normalise(mac or "") not in {
        _normalise(value) for value in selector.macs
    }:
        return False
    if selector.vendors and not vendors.intersection(
        _normalise(value) for value in selector.vendors
    ):
        return False
    if selector.products and not products.intersection(
        _normalise(value) for value in selector.products
    ):
        return False
    return True


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())
