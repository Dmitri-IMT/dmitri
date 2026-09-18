from types import SimpleNamespace
from uuid import uuid4

from api.services.ai.chat import (
    _host_vulnerability_summary,
    _select_findings,
    build_finding_context,
    build_host_context,
    finding_reference_map,
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
    first.finding_id = "first"
    second.finding_id = "second"

    references = finding_reference_map([first, second], "corrigir modbus")

    assert references == {"finding_1": "second", "finding_2": "first"}


def test_host_summary_counts_all_findings_by_equipment() -> None:
    first = _finding("First", "http")
    first.host_ip = "192.168.1.10"
    first.severity = "high"
    second = _finding("Second", "ssh")
    second.host_ip = "192.168.1.10"
    second.severity = "critical"
    third = _finding("Third", "http")
    third.host_ip = "192.168.1.20"
    third.severity = "low"

    summary = _host_vulnerability_summary([first, second, third])

    assert summary[0]["host_ip"] == "192.168.1.10"
    assert summary[0]["finding_count"] == 2
    assert summary[0]["severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 0,
        "low": 0,
    }


def test_finding_context_is_bounded_and_keeps_grounding_fields() -> None:
    finding = _finding("OpenSSH vulnerability", "ssh")
    finding.finding_id = "finding-id"
    finding.description = "A detailed description."
    finding.recommendation = "Update the service."
    finding.evidence = "banner evidence"
    finding.severity = "high"
    finding.host_ip = "192.168.1.10"

    context = build_finding_context(finding)

    assert context["finding"] == {
        "finding_ref": "finding_1",
        "finding_id": "finding-id",
        "title": "OpenSSH vulnerability",
        "description": "A detailed description.",
        "recommendation": "Update the service.",
        "evidence": "banner evidence",
        "severity": "high",
        "risk_score": None,
        "confidence": None,
        "cve_id": None,
        "cvss_score": None,
        "host_ip": "192.168.1.10",
        "host_hostname": None,
        "service": "ssh",
        "port": None,
    }


def test_host_context_contains_machine_facts_and_bounded_findings() -> None:
    host = SimpleNamespace(
        host_id=uuid4(),
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
        title="Modbus exposed",
        severity="critical",
        risk_score=90,
        service="modbus",
        cve_id=None,
        recommendation="Restrict access.",
    )

    context = build_host_context(host, [finding])

    assert context["host"]["ip"] == "192.168.1.10"
    assert context["host"]["services"][0]["port"] == 502
    assert context["findings"][0]["finding_ref"] == "finding_1"
    assert context["findings"][0]["service"] == "modbus"
