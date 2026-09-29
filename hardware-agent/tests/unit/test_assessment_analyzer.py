from __future__ import annotations

import builtins
import json
import socket
import subprocess
import xml.etree.ElementTree as ET
from itertools import permutations

import pytest
from agent.assessment.analyzer import assess_hosts
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.scanner.models import (
    HostInfo,
    MacIdentity,
    OperatingSystemInfo,
    PortInfo,
    ScriptResult,
    ServiceInfo,
)
from agent.targeted.models import (
    TargetedObservation,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.utils.nmap_xml import parse_ports


def _port(
    port: int,
    service: str = "unknown",
    *,
    protocol: str = "tcp",
    state: str = "open",
    product: str = "",
    version: str = "",
    extra_info: str = "",
    cpes: list[str] | None = None,
    scripts: list[ScriptResult] | None = None,
) -> PortInfo:
    return PortInfo(
        port=port,
        protocol=protocol,
        state=state,
        service=ServiceInfo(
            name=service,
            product=product,
            version=version,
            extra_info=extra_info,
            cpes=cpes or [],
        ),
        scripts=scripts or [],
    )


def test_assessment_emits_one_exposure_per_unique_open_endpoint() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(22, "ssh"),
            _port(22, "ssh", product="OpenSSH"),
            _port(23, "telnet", state="closed"),
            _port(80, "http", state="filtered"),
        ],
    )

    result = assess_hosts([host])

    assert [(str(item.ip), item.protocol, item.port) for item in result.exposures] == [
        ("192.168.1.20", "tcp", 22)
    ]
    assert result.exposures[0].observed_version == "OpenSSH"


def test_exposure_roles_attention_and_confidence_are_conservative() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(80, "http"),
            _port(8081, "unknown"),
            _port(3128, "http-proxy"),
            _port(23, "telnet"),
            _port(
                21,
                "ftp",
                scripts=[ScriptResult("ftp-anon", "Anonymous FTP login allowed")],
            ),
            _port(2222, "sftp"),
        ],
    )

    by_port = {item.port: item for item in assess_hosts([host]).exposures}

    assert (by_port[80].role, by_port[80].attention) == (
        "general_service",
        "informational",
    )
    assert (by_port[8081].role, by_port[8081].attention) == ("unknown", "review")
    assert (by_port[3128].role, by_port[3128].attention) == ("proxy", "review")
    assert (by_port[23].role, by_port[23].attention) == (
        "remote_access",
        "priority",
    )
    assert (by_port[21].role, by_port[21].attention) == (
        "file_sharing",
        "priority",
    )
    assert by_port[2222].role == "general_service"
    assert {item.confidence for item in by_port.values()} == {"low"}


def test_exposure_reason_names_cleartext_priority_cause() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[_port(23, "telnet")],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.reason == (
        "The endpoint is classified as remote access from observed service "
        "fingerprint; "
        "attention is priority because accepted evidence indicates a cleartext remote "
        "access channel."
    )


def test_exposure_reason_names_unauthenticated_priority_cause() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                21,
                "ftp",
                scripts=[ScriptResult("ftp-anon", "Anonymous FTP login allowed")],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.reason == (
        "The endpoint is classified as file sharing from observed service fingerprint; "
        "attention is priority because accepted evidence reports an unauthenticated "
        "sensitive surface."
    )


def test_exposure_reason_names_review_role_baseline() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[_port(3128, "http-proxy")],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.reason == (
        "The endpoint is classified as proxy from observed service fingerprint; "
        "attention is review because the proxy role uses the review baseline."
    )


def test_exposure_reason_names_informational_role_baseline() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[_port(80, "http")],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.reason == (
        "The endpoint is classified as general service from identified open service; "
        "attention is informational because the general service role uses the "
        "informational baseline."
    )


def test_cleartext_reason_precedes_unauthenticated_reason_when_both_apply() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                23,
                "telnet",
                scripts=[ScriptResult("ftp-anon", "Anonymous FTP login allowed")],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.attention == "priority"
    assert "cleartext remote access channel" in exposure.reason
    assert "unauthenticated" not in exposure.reason


def test_every_exposure_role_reason_names_its_attention_cause() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8000,
                "http",
                scripts=[ScriptResult("http-title", "Admin Console")],
            ),
            _port(
                8001,
                "https",
                scripts=[ScriptResult("http-title", "Swagger")],
            ),
            _port(3306, "mysql"),
            _port(445, "microsoft-ds"),
            _port(22, "ssh"),
            _port(3128, "http-proxy"),
            _port(502, "modbus"),
            _port(5353, "mdns", protocol="udp"),
            _port(554, "rtsp"),
            _port(80, "http"),
            _port(49152, "unknown"),
        ],
    )

    exposures = assess_hosts([host]).exposures
    by_role = {item.role: item for item in exposures}
    expected_causes = {
        "administration": (
            "priority because accepted evidence indicates a cleartext "
            "administration channel"
        ),
        "api": "review because the api role uses the review baseline",
        "data_store": "review because the data store role uses the review baseline",
        "file_sharing": "review because the file sharing role uses the review baseline",
        "remote_access": (
            "review because the remote access role uses the review baseline"
        ),
        "proxy": "review because the proxy role uses the review baseline",
        "device_control": (
            "priority because accepted evidence indicates a cleartext device "
            "control channel"
        ),
        "discovery": (
            "informational because the discovery role uses the informational baseline"
        ),
        "media": "informational because the media role uses the informational baseline",
        "general_service": (
            "informational because the general service role uses the informational "
            "baseline"
        ),
        "unknown": "review because the unknown role uses the review baseline",
    }

    assert set(by_role) == set(expected_causes)
    for role, expected_cause in expected_causes.items():
        reason = by_role[role].reason
        assert f"classified as {role.replace('_', ' ')}" in reason
        assert expected_cause in reason
        assert len(reason) <= 240


def test_priority_reason_is_deterministic_and_does_not_copy_secret_input() -> None:
    secret = "REASON-SECRET-MUST-NOT-LEAK"
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                21,
                "ftp",
                scripts=[
                    ScriptResult(
                        "ftp-anon",
                        f"Anonymous FTP login allowed; password={secret}",
                    )
                ],
            )
        ],
    )

    first = assess_hosts([host]).exposures[0]
    second = assess_hosts([host]).exposures[0]

    assert first.reason == second.reason
    assert first.reason == (
        "The endpoint is classified as file sharing from observed service fingerprint; "
        "attention is priority because accepted evidence reports an unauthenticated "
        "sensitive surface."
    )
    assert secret not in first.reason


def test_structured_web_evidence_can_identify_admin_or_api_surface() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(8080, "http", scripts=[ScriptResult("http-title", "Admin Console")]),
            _port(8081, "http", scripts=[ScriptResult("http-title", "Swagger")]),
        ],
    )

    by_port = {item.port: item for item in assess_hosts([host]).exposures}

    assert (by_port[8080].role, by_port[8080].attention) == (
        "administration",
        "priority",
    )
    assert (by_port[8081].role, by_port[8081].attention) == ("api", "review")
    assert by_port[8080].confidence == by_port[8081].confidence == "medium"


@pytest.mark.parametrize("port", [3000, 8000, 8888])
def test_cleartext_http_admin_is_priority_on_nonstandard_ports(port: int) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(port, "http", scripts=[ScriptResult("http-title", "Admin Console")])
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "administration"
    assert exposure.attention == "priority"


@pytest.mark.parametrize(
    ("port", "service", "expected_attention"),
    [
        (80, "http", "priority"),
        (443, "http", "priority"),
        (80, "https", "review"),
        (443, "https", "review"),
    ],
)
def test_port_number_does_not_determine_http_encryption(
    port: int,
    service: str,
    expected_attention: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                port,
                service,
                scripts=[ScriptResult("http-title", "Admin Console")],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "administration"
    assert exposure.attention == expected_attention


@pytest.mark.parametrize("service", ["https", "ssl/http"])
def test_tls_admin_is_not_treated_as_cleartext_on_nonstandard_ports(
    service: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8000,
                service,
                scripts=[ScriptResult("http-title", "Admin Console")],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "administration"
    assert exposure.attention == "review"


@pytest.mark.parametrize("tls_script_id", ["ssl-cert", "tls-alpn"])
def test_tls_script_prevents_http_admin_from_being_treated_as_cleartext(
    tls_script_id: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8888,
                "http",
                scripts=[
                    ScriptResult("http-title", "Admin Console"),
                    ScriptResult(tls_script_id, "Accepted TLS evidence"),
                ],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "administration"
    assert exposure.attention == "review"


def test_unstructured_certificate_word_does_not_establish_tls() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                443,
                "http",
                scripts=[
                    ScriptResult(
                        "http-title",
                        "Admin Console certificate management",
                    )
                ],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "administration"
    assert exposure.attention == "priority"


def test_duplicate_endpoint_assessment_is_independent_of_observation_order() -> None:
    admin = _port(
        8080,
        "http",
        scripts=[ScriptResult("http-title", "Admin Console")],
    )
    api = _port(
        8080,
        "http",
        scripts=[ScriptResult("http-title", "Swagger")],
    )

    first = assess_hosts(
        [HostInfo(ip="192.168.1.20", hostname="host", ports=[admin, api])]
    )
    reversed_result = assess_hosts(
        [HostInfo(ip="192.168.1.20", hostname="host", ports=[api, admin])]
    )

    def dump(result) -> str:
        return json.dumps(
            {
                "machine_types": result.machine_types,
                "profiles": {
                    key: value.model_dump(mode="json")
                    for key, value in result.device_profiles.items()
                },
                "exposures": [
                    value.model_dump(mode="json") for value in result.exposures
                ],
            },
            separators=(",", ":"),
        )

    assert dump(first) == dump(reversed_result)
    assert first.exposures[0].role == "api"


def test_equal_richness_duplicate_endpoints_are_fully_deterministic() -> None:
    duplicates = [
        _port(
            8080,
            "http",
            product="Alpha camera",
            version="1.0",
            cpes=["cpe:/h:axis:camera_alpha:1.0"],
            scripts=[ScriptResult("http-title", "Swagger")],
        ),
        _port(
            8080,
            "http",
            product="Beta camera",
            version="2.0",
            cpes=["cpe:/h:axis:camera_beta:2.0"],
            scripts=[
                ScriptResult(
                    "ssl-cert",
                    data={"subject": "Beta camera", "issuer": "Axis CA"},
                )
            ],
        ),
        _port(
            8080,
            "http",
            product="Zulu camera",
            version="3.0",
            cpes=["cpe:/h:axis:camera_zulu:3.0"],
            scripts=[
                ScriptResult(
                    "http-title",
                    "Admin console; Bearer DUPLICATE-ENDPOINT-SECRET",
                )
            ],
        ),
    ]

    serialized_results: set[str] = set()
    assessed_results = []
    for ordered_ports in permutations(duplicates):
        result = assess_hosts(
            [
                HostInfo(
                    ip="192.168.1.20",
                    hostname="axis-camera",
                    identity=MacIdentity(vendor="Axis Communications"),
                    ports=list(ordered_ports),
                )
            ]
        )
        assessed_results.append(result)
        serialized_results.add(
            json.dumps(
                {
                    "machine_types": result.machine_types,
                    "profiles": {
                        key: value.model_dump(mode="json")
                        for key, value in result.device_profiles.items()
                    },
                    "exposures": [
                        value.model_dump(mode="json") for value in result.exposures
                    ],
                },
                separators=(",", ":"),
            )
        )

    assert len(serialized_results) == 1
    result = assessed_results[0]
    profile = result.device_profiles["192.168.1.20"]
    exposure = result.exposures[0]
    serialized = next(iter(serialized_results))

    assert result.machine_types["192.168.1.20"] == "camera"
    assert profile.product_family == "Alpha camera"
    assert exposure.observed_version == "Zulu camera 3.0"
    assert exposure.role == "administration"
    assert any(
        item.kind == "cpe" and item.value == "cpe:/h:axis:camera_zulu:3.0"
        for item in exposure.evidence
    )
    assert any(
        item.kind == "banner"
        and item.value == "Admin console; [REDACTED]"
        for item in exposure.evidence
    )
    assert "DUPLICATE-ENDPOINT-SECRET" not in serialized


def test_profile_score_thresholds_and_conflict_are_visible() -> None:
    confident_camera = HostInfo(
        ip="192.168.1.20",
        hostname="axis-camera",
        identity=MacIdentity(vendor="Axis Communications"),
        ports=[_port(554, "rtsp", product="Axis camera")],
        operating_system=OperatingSystemInfo(
            name="Embedded Linux",
            accuracy=95,
            device_type="camera",
        ),
    )
    conflicting = HostInfo(
        ip="192.168.1.21",
        hostname="mixed",
        identity=MacIdentity(vendor="Axis Communications"),
        ports=[_port(554, "rtsp"), _port(22, "ssh", product="server")],
        operating_system=OperatingSystemInfo(
            name="Linux",
            accuracy=95,
            device_type="server",
        ),
    )

    result = assess_hosts([conflicting, confident_camera])

    assert result.machine_types[confident_camera.ip] == "camera"
    assert result.device_profiles[confident_camera.ip].confidence == "high"
    assert result.machine_types[conflicting.ip] == "unknown"
    assert result.device_profiles[conflicting.ip].confidence == "low"
    assert any(
        "Machine-type evidence is close" in item
        for item in result.device_profiles[conflicting.ip].conflicts
    )


def test_unknown_and_randomized_mac_never_invent_identity() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="192.168.1.20",
        identity=MacIdentity(mac="02:11:22:33:44:55", vendor="Axis Communications"),
        ports=[_port(65000)],
    )

    result = assess_hosts([host])
    profile = result.device_profiles[host.ip]

    assert result.machine_types[host.ip] == "unknown"
    assert profile.manufacturer is None
    assert profile.product_family is None
    assert profile.model is None
    assert profile.confidence == "unknown"
    assert "Locally administered MAC address; OUI manufacturer unavailable." in (
        profile.limitations
    )


def test_modbus_identity_sets_products_without_inventing_machine_type() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="plc",
        ports=[_port(502, "modbus")],
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
                            model_name="M340",
                        ),
                    )
                ],
            )
        ],
    )

    result = assess_hosts([host])
    profile = result.device_profiles[host.ip]

    assert result.machine_types[host.ip] == "unknown"
    assert profile.manufacturer == "Schneider Electric"
    assert profile.product_family == "BMX P34"
    assert profile.model == "BMX P34"
    assert result.exposures[0].role == "device_control"
    assert result.exposures[0].confidence == "high"


def test_modbus_protocol_evidence_prioritizes_nonstandard_control_channel() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[
            _port(
                1502,
                "unknown",
                scripts=[ScriptResult("modbus-discover", "Modbus device")],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "device_control"
    assert exposure.confidence == "high"
    assert exposure.attention == "priority"


def test_confirmed_modbus_identity_prioritizes_nonstandard_control_channel() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[_port(1502, "unknown")],
        industrial_services=[
            ModbusService(port=1502, confidence="confirmed")
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "device_control"
    assert exposure.confidence == "high"
    assert exposure.attention == "priority"


def test_confirmed_modbus_identity_only_enriches_matching_tcp_endpoint() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[
            _port(1502, "unknown", protocol="udp"),
            _port(1502, "unknown", protocol="tcp"),
        ],
        industrial_services=[
            ModbusService(port=1502, confidence="confirmed")
        ],
    )

    exposures = {
        exposure.protocol: exposure for exposure in assess_hosts([host]).exposures
    }

    assert exposures["tcp"].role == "device_control"
    assert exposures["tcp"].confidence == "high"
    assert exposures["tcp"].attention == "priority"
    assert any(
        item.kind == "industrial" for item in exposures["tcp"].evidence
    )
    assert exposures["udp"].role == "unknown"
    assert exposures["udp"].confidence == "low"
    assert exposures["udp"].attention == "review"
    assert all(
        item.kind != "industrial" for item in exposures["udp"].evidence
    )


@pytest.mark.parametrize(
    ("ports", "industrial_services", "expected"),
    [
        pytest.param(
            [_port(1502, protocol="tcp")],
            [ModbusService(port=1502, confidence="confirmed")],
            {("tcp", 1502): ("device_control", "high", True)},
            id="tcp-only-confirmed",
        ),
        pytest.param(
            [_port(1502, protocol="udp")],
            [ModbusService(port=1502, confidence="confirmed")],
            {("udp", 1502): ("unknown", "low", False)},
            id="udp-only-confirmed-does-not-enrich",
        ),
        pytest.param(
            [
                _port(1502, protocol="udp"),
                _port(1502, protocol="tcp"),
            ],
            [ModbusService(port=1502, confidence="suspected")],
            {
                ("tcp", 1502): ("unknown", "low", False),
                ("udp", 1502): ("unknown", "low", False),
            },
            id="same-number-suspected-does-not-enrich-either-protocol",
        ),
        pytest.param(
            [
                _port(1502, protocol="udp"),
                _port(2502, protocol="tcp"),
            ],
            [ModbusService(port=1502, confidence="confirmed")],
            {
                ("tcp", 2502): ("unknown", "low", False),
                ("udp", 1502): ("unknown", "low", False),
            },
            id="confirmed-service-does-not-cross-protocol-or-port",
        ),
    ],
)
def test_modbus_service_association_is_tcp_port_specific(
    ports: list[PortInfo],
    industrial_services: list[ModbusService],
    expected: dict[tuple[str, int], tuple[str, str, bool]],
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=ports,
        industrial_services=industrial_services,
    )

    actual = {}
    for exposure in assess_hosts([host]).exposures:
        actual[(exposure.protocol, exposure.port)] = (
            exposure.role,
            exposure.confidence,
            any(item.kind == "industrial" for item in exposure.evidence),
        )

    assert actual == expected


def test_udp_modbus_discover_is_endpoint_evidence_not_service_enrichment() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[
            _port(
                1502,
                protocol="udp",
                scripts=[ScriptResult("modbus-discover", "Modbus device")],
            )
        ],
        industrial_services=[
            ModbusService(port=1502, confidence="confirmed")
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.protocol == "udp"
    assert exposure.role == "device_control"
    assert exposure.confidence == "high"
    assert exposure.attention == "priority"
    assert any(item.kind == "protocol" for item in exposure.evidence)
    assert all(item.kind != "industrial" for item in exposure.evidence)


def test_modbus_association_is_stable_for_port_and_service_ordering() -> None:
    ports = [
        _port(1502, protocol="udp"),
        _port(2502, protocol="tcp"),
        _port(1502, protocol="tcp"),
    ]
    services = [
        ModbusService(port=2502, confidence="suspected"),
        ModbusService(port=1502, confidence="confirmed"),
    ]
    observed = []

    for ordered_ports in (ports, list(reversed(ports))):
        for ordered_services in (services, list(reversed(services))):
            host = HostInfo(
                ip="192.168.1.20",
                hostname="controller",
                ports=ordered_ports,
                industrial_services=ordered_services,
            )
            observed.append(
                [
                    exposure.model_dump(mode="json")
                    for exposure in assess_hosts([host]).exposures
                ]
            )

    assert all(result == observed[0] for result in observed[1:])
    assert [
        (exposure["protocol"], exposure["port"])
        for exposure in observed[0]
    ] == [("tcp", 1502), ("tcp", 2502), ("udp", 1502)]


@pytest.mark.parametrize(
    ("port", "industrial_services"),
    [
        pytest.param(502, [], id="port-only"),
        pytest.param(
            1502,
            [ModbusService(port=1502, confidence="suspected")],
            id="suspected-industrial-identity",
        ),
        pytest.param(
            1502,
            [ModbusService(port=502, confidence="confirmed")],
            id="confirmed-industrial-identity-for-another-endpoint",
        ),
    ],
)
def test_unconfirmed_modbus_evidence_does_not_request_priority(
    port: int,
    industrial_services: list[ModbusService],
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[_port(port, "unknown")],
        industrial_services=industrial_services,
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.attention == "review"


def test_generic_script_output_does_not_confirm_modbus_protocol() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[
            _port(
                1502,
                "unknown",
                scripts=[ScriptResult("banner", "Possible Modbus device")],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "unknown"
    assert exposure.attention == "review"


@pytest.mark.parametrize(
    ("scripts", "industrial_services"),
    [
        pytest.param(
            [
                ScriptResult("modbus-discover", "Modbus device"),
                ScriptResult("ssl-cert", "Accepted TLS evidence"),
            ],
            [],
            id="protocol-script-with-tls",
        ),
        pytest.param(
            [ScriptResult("ssl-cert", "Accepted TLS evidence")],
            [ModbusService(port=1502, confidence="confirmed")],
            id="confirmed-identity-with-tls",
        ),
    ],
)
def test_tls_protected_modbus_control_channel_is_not_priority(
    scripts: list[ScriptResult],
    industrial_services: list[ModbusService],
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="controller",
        ports=[_port(1502, "unknown", scripts=scripts)],
        industrial_services=industrial_services,
    )

    exposure = assess_hosts([host]).exposures[0]

    assert exposure.role == "device_control"
    assert exposure.attention == "review"


def test_secret_bodies_are_omitted_and_all_assessment_values_are_bounded() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="camera-" + "h" * 300,
        identity=MacIdentity(vendor="Axis Communications " + "v" * 300),
        ports=[
            _port(
                554,
                "rtsp",
                product="Axis camera " + "p" * 300,
                extra_info="token=do-not-copy",
                scripts=[
                    ScriptResult("http-title", "password=do-not-copy"),
                    ScriptResult(
                        "ssl-cert",
                        data={"subject": "camera.local", "issuer": "i" * 300},
                    ),
                ],
            )
        ],
    )

    result = assess_hosts([host])
    serialized = json.dumps(
        {
            "profile": result.device_profiles[host.ip].model_dump(mode="json"),
            "exposures": [item.model_dump(mode="json") for item in result.exposures],
        }
    )

    assert "do-not-copy" not in serialized
    profile = result.device_profiles[host.ip]
    assert len(profile.evidence) <= 12
    assert all(
        len(item.source) <= 80 and len(item.value) <= 160
        for item in profile.evidence
    )
    assert all(len(item.reason) <= 240 for item in result.exposures)


def test_exposure_uses_only_compact_version_sources_and_omits_credentials() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                22,
                "ssh",
                product="OpenSSH",
                version="9.6",
                extra_info="Authorization Bearer TOPSECRET",
            ),
            _port(
                443,
                "https",
                product="Authorization Bearer PRODUCTSECRET",
                version="token TOKEN-SECRET",
                extra_info="password PASSWORD-SECRET",
                cpes=["cpe:/a:vendor:safe_product:1.0"],
            ),
        ],
    )

    by_port = {item.port: item for item in assess_hosts([host]).exposures}

    assert by_port[22].observed_version == "OpenSSH 9.6"
    assert by_port[443].observed_version == "cpe:/a:vendor:safe_product:1.0"
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in by_port.values()]
    )
    assert "TOPSECRET" not in serialized
    assert "PRODUCTSECRET" not in serialized
    assert "TOKEN-SECRET" not in serialized
    assert "PASSWORD-SECRET" not in serialized


@pytest.mark.parametrize(
    "credential_text",
    [
        pytest.param(
            "Authorization: Bearer HEADER-COLON-SECRET",
            id="authorization-colon-bearer",
        ),
        pytest.param(
            "authorization=Bearer HEADER-EQUALS-SECRET",
            id="authorization-equals-bearer",
        ),
        pytest.param(
            "Authorization Bearer HEADER-SPACE-SECRET",
            id="authorization-space-bearer",
        ),
        pytest.param("Bearer STANDALONE-BEARER-SECRET", id="standalone-bearer"),
        pytest.param("Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==", id="standalone-basic"),
    ],
)
def test_authorization_variants_cannot_enter_assessment_output(
    credential_text: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                443,
                "https",
                product="Camera gateway",
                version="1.2.3",
                extra_info=credential_text,
                scripts=[ScriptResult("http-title", credential_text)],
            )
        ],
    )

    result = assess_hosts([host])
    exposure = result.exposures[0]
    serialized = json.dumps(
        {
            "profile": result.device_profiles[host.ip].model_dump(mode="json"),
            "exposure": exposure.model_dump(mode="json"),
        }
    )

    assert exposure.observed_version == "Camera gateway 1.2.3"
    assert credential_text not in serialized
    assert "SECRET" not in serialized


def test_credential_redaction_preserves_safe_adjacent_evidence() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8080,
                "http",
                scripts=[
                    ScriptResult(
                        "http-title",
                        "Admin console; Bearer STANDALONE-SECRET",
                    )
                ],
            )
        ],
    )

    result = assess_hosts([host])
    exposure = result.exposures[0]
    evidence_values = [item.value for item in exposure.evidence]

    assert exposure.role == "administration"
    assert any("Admin console; [REDACTED]" == value for value in evidence_values)
    assert all("STANDALONE-SECRET" not in value for value in evidence_values)


@pytest.mark.parametrize(
    "description",
    [
        pytest.param(
            "Admin console uses Basic authentication",
            id="basic-authentication",
        ),
        pytest.param(
            "API supports Bearer authentication",
            id="bearer-authentication",
        ),
        pytest.param(
            "Admin console sends a Basic realm challenge",
            id="basic-realm",
        ),
    ],
)
def test_auth_scheme_descriptions_remain_safe_evidence(description: str) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8080,
                "http",
                scripts=[
                    ScriptResult(
                        "http-title",
                        description,
                    )
                ],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert any(item.value == description for item in exposure.evidence)


@pytest.mark.parametrize(
    "description",
    [
        "API token rotation policy",
        "Cookie policy for users",
        "Secret management console",
    ],
)
def test_security_terms_without_credential_values_remain_evidence(
    description: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8080,
                "http",
                scripts=[ScriptResult("http-title", description)],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert any(item.value == description for item in exposure.evidence)


@pytest.mark.parametrize(
    "description",
    [
        "Password rotation policy",
        "Token management policy",
        "API key rotation policy",
        "Authorization policy overview",
        "Cookie management policy",
    ],
)
def test_safe_security_terminology_is_not_mistaken_for_a_credential(
    description: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8080,
                "http",
                scripts=[ScriptResult("http-title", description)],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]

    assert any(item.value == description for item in exposure.evidence)


@pytest.mark.parametrize(
    "credential_text",
    [
        "Admin portal; password: DELIMITER-PASSWORD",
        "Admin portal; passwd=DELIMITER-PASSWD",
        "Admin portal; token : Bearer DELIMITER-TOKEN",
        "Admin portal; secret=DELIMITER-SECRET",
        "Admin portal; api-key: DELIMITER-API-KEY",
        "Admin portal; api_key=DELIMITER-API-KEY-UNDERSCORE",
        "Admin portal; api key: DELIMITER-API-KEY-SPACE",
        "Admin portal; Authorization: Basic DELIMITER-AUTHORIZATION",
        "Admin portal; cookie=DELIMITER-COOKIE",
        "Admin portal; BEARER DELIMITER-STANDALONE-BEARER",
        "Admin portal; Basic DELIMITER-STANDALONE-BASIC",
    ],
)
def test_delimited_and_standalone_credentials_are_redacted(
    credential_text: str,
) -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(
                8080,
                "http",
                scripts=[ScriptResult("http-title", credential_text)],
            )
        ],
    )

    exposure = assess_hosts([host]).exposures[0]
    serialized = json.dumps(exposure.model_dump(mode="json"))

    assert "Admin portal" in serialized
    assert "DELIMITER-" not in serialized


def test_cpe_and_certificate_can_supply_corroborated_product_family() -> None:
    cpe_host = HostInfo(
        ip="192.168.1.20",
        hostname="axis-camera",
        ports=[_port(554, "rtsp", cpes=["cpe:/h:axis:camera_family:1.0"])],
    )
    certificate_host = HostInfo(
        ip="192.168.1.21",
        hostname="printer",
        identity=MacIdentity(vendor="Brother"),
        ports=[
            _port(
                631,
                "ipp",
                scripts=[
                    ScriptResult(
                        "ssl-cert",
                        data={"subject": "Brother printer family"},
                    )
                ],
            )
        ],
    )

    result = assess_hosts([certificate_host, cpe_host])

    assert result.device_profiles[cpe_host.ip].product_family == (
        "cpe:/h:axis:camera_family:1.0"
    )
    assert result.device_profiles[certificate_host.ip].product_family == (
        "subject: Brother printer family"
    )


def test_nested_nmap_certificate_common_name_supplies_bounded_family() -> None:
    host_element = ET.fromstring(
        """
        <host>
          <ports>
            <port protocol="tcp" portid="631">
              <state state="open" />
              <service name="ipp" />
              <script id="ssl-cert" output="Certificate details">
                <table key="subject">
                  <elem key="commonName">Brother printer family</elem>
                  <elem key="organizationName">Not copied</elem>
                </table>
                <table key="issuer">
                  <elem key="commonName">Brother printer CA</elem>
                  <elem key="organizationName">Not copied</elem>
                </table>
                <elem key="sha1">not-copied-fingerprint</elem>
              </script>
            </port>
          </ports>
        </host>
        """
    )
    host = HostInfo(
        ip="192.168.1.21",
        hostname="printer",
        identity=MacIdentity(vendor="Brother"),
        ports=parse_ports(host_element),
    )

    result = assess_hosts([host])
    profile = result.device_profiles[host.ip]
    serialized = json.dumps(profile.model_dump(mode="json"))

    assert profile.product_family == "subject: Brother printer family"
    assert any(
        item.kind == "certificate"
        and item.value == "subject: Brother printer family"
        for item in profile.evidence
    )
    assert "Brother printer CA" in serialized
    assert "Not copied" not in serialized
    assert "not-copied-fingerprint" not in serialized


def test_nested_certificate_common_names_are_bounded_and_only_subject_sets_family(
) -> None:
    subject_common_name = "Brother printer family " + "s" * 200
    issuer_common_name = "Axis camera issuer " + "i" * 200
    host_element = ET.fromstring(
        f"""
        <host>
          <ports>
            <port protocol="tcp" portid="631">
              <state state="open" />
              <service name="ipp" />
              <script id="ssl-cert" output="Certificate details">
                <table key="subject">
                  <elem key="commonName">{subject_common_name}</elem>
                  <elem key="organizationName">SUBJECT-DISALLOWED-SECRET</elem>
                </table>
                <table key="issuer">
                  <elem key="commonName">{issuer_common_name}</elem>
                  <elem key="organizationalUnitName">ISSUER-DISALLOWED-SECRET</elem>
                </table>
                <elem key="sha256">FINGERPRINT-DISALLOWED-SECRET</elem>
              </script>
            </port>
          </ports>
        </host>
        """
    )
    host = HostInfo(
        ip="192.168.1.21",
        hostname="printer",
        identity=MacIdentity(vendor="Brother"),
        ports=parse_ports(host_element),
    )

    result = assess_hosts([host])
    profile = result.device_profiles[host.ip]
    serialized = json.dumps(profile.model_dump(mode="json"))
    certificate_values = [
        item.value for item in profile.evidence if item.kind == "certificate"
    ]

    assert profile.product_family is not None
    assert profile.product_family.startswith("subject: Brother printer family")
    assert "Axis camera issuer" not in profile.product_family
    assert len(profile.product_family) <= 160
    assert certificate_values
    assert all(len(value) <= 160 for value in certificate_values)
    assert any(
        value.startswith("subject: Brother printer family")
        for value in certificate_values
    )
    assert any(
        value.startswith("issuer: Axis camera issuer")
        for value in certificate_values
    )
    assert "SUBJECT-DISALLOWED-SECRET" not in serialized
    assert "ISSUER-DISALLOWED-SECRET" not in serialized
    assert "FINGERPRINT-DISALLOWED-SECRET" not in serialized


def test_nested_certificate_fact_order_is_independent_of_xml_child_order() -> None:
    def assessed_profile(subject_first: bool) -> str:
        subject = """
          <table key="subject">
            <elem key="commonName">Brother printer family</elem>
            <elem key="organizationName">Not copied</elem>
          </table>
        """
        issuer = """
          <table key="issuer">
            <elem key="commonName">Brother printer CA</elem>
            <elem key="organizationName">Not copied</elem>
          </table>
        """
        certificate_children = subject + issuer if subject_first else issuer + subject
        host_element = ET.fromstring(
            f"""
            <host>
              <ports>
                <port protocol="tcp" portid="631">
                  <state state="open" />
                  <service name="ipp" />
                  <script id="ssl-cert" output="Certificate details">
                    {certificate_children}
                  </script>
                </port>
              </ports>
            </host>
            """
        )
        host = HostInfo(
            ip="192.168.1.21",
            hostname="printer",
            identity=MacIdentity(vendor="Brother"),
            ports=parse_ports(host_element),
        )
        profile = assess_hosts([host]).device_profiles[host.ip]
        return json.dumps(profile.model_dump(mode="json"), separators=(",", ":"))

    assert assessed_profile(subject_first=True) == assessed_profile(subject_first=False)


def test_uncorroborated_or_unmatched_product_facts_cannot_invent_family() -> None:
    uncorroborated_cpe = HostInfo(
        ip="192.168.1.20",
        hostname="host",
        ports=[
            _port(65000, "unknown", cpes=["cpe:/h:axis:camera_family:1.0"])
        ],
    )
    unmatched_cpe = HostInfo(
        ip="192.168.1.21",
        hostname="camera",
        ports=[
            _port(554, "rtsp", cpes=["cpe:/h:vendor:generic_appliance:1.0"])
        ],
    )
    unmatched_certificate = HostInfo(
        ip="192.168.1.22",
        hostname="printer",
        identity=MacIdentity(vendor="Brother"),
        ports=[
            _port(
                631,
                "ipp",
                scripts=[
                    ScriptResult(
                        "ssl-cert",
                        data={"subject": "Generic appliance family"},
                    )
                ],
            )
        ],
    )

    result = assess_hosts(
        [unmatched_certificate, unmatched_cpe, uncorroborated_cpe]
    )

    assert result.machine_types[uncorroborated_cpe.ip] == "camera"
    assert result.device_profiles[uncorroborated_cpe.ip].product_family is None
    assert result.machine_types[unmatched_cpe.ip] == "camera"
    assert result.device_profiles[unmatched_cpe.ip].product_family is None
    assert result.machine_types[unmatched_certificate.ip] == "printer"
    assert result.device_profiles[unmatched_certificate.ip].product_family is None


def test_assessment_is_deterministic_and_does_not_perform_io(monkeypatch) -> None:
    hosts = [
        HostInfo(
            ip="192.168.1.21",
            hostname="printer",
            identity=MacIdentity(vendor="Brother"),
            ports=[_port(9100, "jetdirect"), _port(631, "ipp")],
        ),
        HostInfo(
            ip="192.168.1.20",
            hostname="camera",
            identity=MacIdentity(vendor="Axis Communications"),
            ports=[_port(8554, "rtsp"), _port(554, "rtsp")],
        ),
    ]
    original_open = builtins.open

    def forbidden(*args, **kwargs):
        raise AssertionError("assessment attempted external I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    try:
        first = assess_hosts(hosts)
        second = assess_hosts(list(reversed(hosts)))
    finally:
        monkeypatch.setattr(builtins, "open", original_open)

    def dump(result) -> str:
        return json.dumps(
            {
                "machine_types": result.machine_types,
                "profiles": {
                    key: value.model_dump(mode="json")
                    for key, value in result.device_profiles.items()
                },
                "exposures": [
                    value.model_dump(mode="json") for value in result.exposures
                ],
            },
            separators=(",", ":"),
        )

    assert dump(first) == dump(second)
    assert [str(item.ip) for item in first.exposures] == sorted(
        str(item.ip) for item in first.exposures
    )


def _targeted_observation_host(
    observations: list[TargetedObservation],
) -> HostInfo:
    return HostInfo(
        ip="192.168.1.90",
        hostname="gateway",
        ports=[_port(8080, "http")],
        targeted_results=[
            TargetedUnitResult(
                TargetedUnit(
                    "192.168.1.90", 8080, "tcp", "http", TargetedTool.FFUF
                ),
                TargetedOutcome.COMPLETED,
                observations=observations,
            )
        ],
    )


@pytest.mark.parametrize(
    ("kind", "rule", "expected_role"),
    [
        ("administration", "WEB-ADMIN-001", "administration"),
        ("api_surface", "WEB-API-DOCS-001", "api"),
    ],
)
def test_targeted_web_observation_enriches_one_existing_exposure(
    kind: str, rule: str, expected_role: str
) -> None:
    observation = TargetedObservation(
        observation_key=f"web:{rule.lower()}",
        kind=kind,  # type: ignore[arg-type]
        summary="Validated web surface",
        evidence=f"2026-09-15.1:{rule}; path=/admin",
        path="/admin",
        rule_id=rule,
        policy_version="2026-09-15.1",
    )
    host = _targeted_observation_host([observation])

    result = assess_hosts([host])

    assert len(result.exposures) == 1
    exposure = result.exposures[0]
    assert exposure.role == expected_role
    assert exposure.confidence == "high"
    assert any(
        item.kind == "web_path"
        and item.source == f"ffuf:{rule}@2026-09-15.1"
        and item.value == "/admin"
        for item in exposure.evidence
    )


def test_targeted_web_observation_uses_structured_fields_not_evidence_blob() -> None:
    observation = TargetedObservation(
        observation_key="web:administration:/admin",
        kind="administration",
        summary="Validated web surface",
        evidence="unrelated blob without path= or rule markers",
        path="/admin",
        rule_id="WEB-ADMIN-001",
        policy_version="2026-09-15.1",
    )
    host = _targeted_observation_host([observation])

    result = assess_hosts([host])

    exposure = result.exposures[0]
    assert any(
        item.kind == "web_path"
        and item.source == "ffuf:WEB-ADMIN-001@2026-09-15.1"
        and item.value == "/admin"
        for item in exposure.evidence
    )


def test_targeted_device_identity_updates_supported_profile_evidence_only() -> None:
    observation = TargetedObservation(
        observation_key="modbus:device-id",
        kind="device_identity",
        summary="Acme PLC-42",
        evidence="vendor=Acme; model=PLC-42",
    )
    host = HostInfo(
        ip="192.168.1.91",
        hostname="controller",
        ports=[_port(502, "modbus")],
        targeted_results=[
            TargetedUnitResult(
                TargetedUnit(
                    "192.168.1.91", 502, "tcp", "modbus", TargetedTool.TESTSSL
                ),
                TargetedOutcome.COMPLETED,
                observations=[observation],
            )
        ],
    )

    result = assess_hosts([host])

    profile = result.device_profiles[host.ip]
    assert profile.product_family == "Acme PLC-42"
    assert any(
        item.kind == "industrial"
        and item.source == "targeted:modbus:device-id"
        and item.value == "Acme PLC-42"
        for item in profile.evidence
    )
    assert len(result.exposures) == 1


def test_targeted_observations_do_not_change_finding_counts() -> None:
    host = _targeted_observation_host(
        [
            TargetedObservation(
                "web:admin",
                "administration",
                "Admin console",
                "2026-09-15.1:WEB-ADMIN-001; path=/admin",
                path="/admin",
                rule_id="WEB-ADMIN-001",
                policy_version="2026-09-15.1",
            )
        ]
    )

    from agent.normalize.findings import extract_findings

    assert extract_findings([host]) == []
