"""Normalization helpers for transforming Nmap output into shared contracts."""

from .contracts import (
    FindingPayload,
    HostPayload,
    ModbusDeviceIdentificationPayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    OperatingSystemDetection,
    PortPayload,
    ScanPayload,
)
from .findings import extract_findings

__all__ = [
    "FindingPayload",
    "HostPayload",
    "ModbusDeviceIdentificationPayload",
    "ModbusTcpServicePayload",
    "ModbusUnitPayload",
    "OperatingSystemDetection",
    "PortPayload",
    "ScanPayload",
    "extract_findings",
]
