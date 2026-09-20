from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from api.schemas.ai import ProviderAIChatResponse
from api.schemas.read import SeverityBreakdown
from api.services.ai.chat import (
    _select_findings,
    build_finding_chat_bundle,
    build_host_chat_bundle,
    build_scan_chat_bundle,
    finding_reference_map,
    materialize_chat_response,
)


def _finding(title: str, service: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        description="description",
        recommendation="recommendation",
        service=service,
        cve_id=None,
        host_ip=None,
        host_hostname=None,
        host_id=None,
        finding_id=uuid4(),
        cvss_score=None,
        severity="medium",
        confidence=None,
        risk_score=None,
        exploitability=None,
    )


def test_question_relevance_moves_matching_finding_to_front() -> None:
    findings = [_finding("Atualizar OpenSSH"), _finding("Senha fraca", "modbus")]

    selected = _select_findings(findings, "o que devo corrigir no modbus?")

    assert selected[0].service == "modbus"
    assert selected[1].title == "Atualizar OpenSSH"


def test_question_selection_remains_bounded_and_stable_without_terms() -> None:
    findings = [_finding("Primeiro"), _finding("Segundo")]

    selected = _select_findings(findings, "e de um")

    assert selected == findings


def test_reference_map_uses_the_same_question_order_as_context() -> None:
    first = _finding("Atualizar OpenSSH", "ssh")
    second = _finding("Senha fraca", "modbus")
    first.finding_id = uuid4()
    second.finding_id = uuid4()

    references = finding_reference_map([first, second], "corrigir modbus")

    assert references["finding_1"] == second.finding_id
    assert references["finding_2"] == first.finding_id


def test_machine_summary_counts_findings_by_machine_ref() -> None:
    host_id = uuid4()
    first = _finding("First", "http")
    first.host_id = host_id
    first.severity = "high"
    second = _finding("Second", "ssh")
    second.host_id = host_id
    second.severity = "critical"
    third = _finding("Third", "http")
    third.host_id = uuid4()
    third.severity = "low"
    detail = SimpleNamespace(
        scan_mode="quick",
        status="completed",
        host_count=2,
        findings=[first, second, third],
    )
    risk = SimpleNamespace(
        total_findings=3,
        scored_findings=3,
        confirmed_findings=0,
        kev_findings=0,
        average_risk_score=50,
        max_risk_score=90,
        severity=SeverityBreakdown(critical=1, high=1, low=1),
    )

    bundle = build_scan_chat_bundle(detail, risk)

    summary = bundle.provider_context["machine_vulnerability_summary"]
    assert summary[0]["machine_ref"] == "machine_1"
    assert summary[0]["finding_count"] == 2


def test_finding_chat_bundle_uses_placeholders_only() -> None:
    finding = _finding("OpenSSH vulnerability", "ssh")
    finding.severity = "high"
    finding.host_ip = "192.168.1.10"
    finding.host_id = uuid4()

    bundle = build_finding_chat_bundle(finding)

    payload = json.dumps(bundle.provider_context)
    assert str(finding.finding_id) not in payload
    assert finding.title not in payload
    assert "192.168.1.10" not in payload
    assert bundle.provider_context["finding"]["finding_ref"] == "finding_1"


def test_host_chat_bundle_uses_machine_and_service_refs() -> None:
    host_id = uuid4()
    host = SimpleNamespace(
        host_id=host_id,
        ip="192.168.1.10",
        hostname="plc-01",
        vendor="Acme",
        machine_type="plc",
        vulnerability_count=2,
        highest_severity="critical",
        open_ports_count=2,
        ports=[
            SimpleNamespace(
                port=502, protocol="tcp", service="modbus", version="1.0"
            )
        ],
    )
    finding = SimpleNamespace(
        finding_id=uuid4(),
        host_id=host_id,
        title="Modbus exposed",
        severity="critical",
        risk_score=90,
        service="modbus",
        cve_id=None,
        cvss_score=None,
        confidence=None,
        exploitability=None,
        host_ip="192.168.1.10",
        host_hostname="plc-01",
    )

    bundle = build_host_chat_bundle(host, [finding])

    payload = json.dumps(bundle.provider_context)
    assert "192.168.1.10" not in payload
    assert "plc-01" not in payload
    assert str(host_id) not in payload
    assert bundle.provider_context["machine_ref"] == "machine_1"
    assert bundle.provider_context["services"][0]["service_ref"] == "service_1"


def test_materialize_chat_response_substitutes_display_values() -> None:
    finding_id = uuid4()
    response = materialize_chat_response(
        ProviderAIChatResponse(
            answer="Revise finding_1 on machine_1.",
            uncertainties=["machine_1 may need follow-up."],
            referenced_finding_refs=["finding_1"],
        ),
        {"finding_1": finding_id},
        {
            "finding_1": "Weak SSH configuration",
            "machine_1": "edge-router",
        },
    )

    assert response.answer == "Revise Weak SSH configuration on edge-router."
    assert response.referenced_finding_ids == [finding_id]
