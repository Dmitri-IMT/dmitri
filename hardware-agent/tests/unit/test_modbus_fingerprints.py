from __future__ import annotations

import pytest
from agent.ot.modbus.fingerprints import (
    FINGERPRINT_EVIDENCE_SOURCE,
    correlate_fc43_fingerprints,
    fingerprint_identification,
)
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo


@pytest.mark.parametrize(
    ("product", "version", "family", "cpe_product"),
    [
        ("BMX P34", "V2.60", "Modicon M340", "modicon_m340_firmware:2.60"),
        ("Modicon M580", "3.10", "Modicon M580", "modicon_m580_firmware:3.10"),
    ],
)
def test_reviewed_schneider_fingerprint_produces_versioned_firmware_cpe(
    product: str,
    version: str,
    family: str,
    cpe_product: str,
) -> None:
    candidate = fingerprint_identification(
        ModbusDeviceIdentification(
            vendor_name="Schneider Electric",
            product_code=product,
            major_minor_revision=version,
        )
    )

    assert candidate is not None
    assert candidate.family == family
    assert candidate.confidence == "high"
    assert cpe_product in candidate.cpe


@pytest.mark.parametrize(
    "identification",
    [
        ModbusDeviceIdentification(
            vendor_name="Schneider Electric", product_code="BMX P34"
        ),
        ModbusDeviceIdentification(
            vendor_name="Schneider Electric",
            product_code="unknown",
            major_minor_revision="2.60",
        ),
        ModbusDeviceIdentification(
            vendor_name="Other Vendor",
            product_code="BMX P34",
            major_minor_revision="2.60",
        ),
        ModbusDeviceIdentification(
            vendor_name="Schneider Electric",
            product_code="BMX P34",
            major_minor_revision="firmware 2.60 build 4",
        ),
    ],
)
def test_ambiguous_or_incomplete_identification_never_guesses_a_cpe(
    identification: ModbusDeviceIdentification,
) -> None:
    assert fingerprint_identification(identification) is None


def test_candidate_is_attached_to_the_matching_port_with_provenance() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        industrial_services=[
            ModbusService(
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
                        identification_sources=["pymodbus-fc43"],
                    )
                ],
            )
        ],
    )

    candidates = correlate_fc43_fingerprints(host)

    assert len(candidates) == 1
    assert host.ports[0].service.cpes == [candidates[0].cpe]
    assert (
        FINGERPRINT_EVIDENCE_SOURCE
        in host.industrial_services[0].evidence_sources
    )


def test_non_fc43_identification_is_not_used_for_fc43_correlation() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        industrial_services=[
            ModbusService(
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
                        identification_sources=["modbus-discover"],
                    )
                ],
            )
        ],
    )

    assert correlate_fc43_fingerprints(host) == []
    assert host.ports[0].service.cpes == []
