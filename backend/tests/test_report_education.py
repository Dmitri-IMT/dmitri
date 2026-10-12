"""Verify attribution, evidence boundaries and complete educational coverage."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from api.models.persistence import EnrichmentJobRecord, NvdCacheRecord
from api.schemas.read import ExposureRead
from api.services.read import get_scan_detail
from api.services.report_education import (
    build_report_education,
    device_identity,
    service_family,
)
from api.services.report_education_copy import guide, text
from api.services.report_education_pdf import EvidenceBars
from api.services.reports import build_scan_report
from read_factories import make_scan, seed_read_graph


@pytest.mark.parametrize("language", ["en", "pt-BR", "ru"])
def test_device_identity_preserves_scan_confidence_without_inventing_model(language):
    identity = device_identity(
        address="192.0.2.1", hostname="192.0.2.1", machine_type="computer",
        os_name="Linux 2.6.32", language=language,
        profile={"manufacturer": "Network adapter vendor", "confidence": "low",
                 "evidence": [{"value": "Linux fingerprint"}]},
    )
    assert "Linux" in identity["display_name"]
    assert "192.0.2.1" not in identity["display_name"]
    assert "Network adapter vendor" not in identity["display_name"]
    assert identity["identity_confidence"] == "low"
    assert identity["model"] is None
    assert identity["identity_evidence"] == ["Linux fingerprint"]


def test_industrial_model_is_used_only_when_reported_by_scan():
    identity = device_identity(
        address="192.0.2.1", hostname="192.0.2.1", machine_type="unknown",
        os_name=None, language="pt-BR",
        profile={"manufacturer": "Schneider Electric", "model": "Modicon M340",
                 "confidence": "high"},
    )
    assert identity["display_name"] == "Schneider Electric Modicon M340"
    unknown = device_identity(
        address="192.0.2.1", hostname="192.0.2.1", machine_type=None,
        os_name=None, profile=None, language="pt-BR",
    )
    assert unknown["display_name"] == text("identity_type_unknown", "pt-BR")
    assert unknown["identity_confidence"] == "unknown"


def _detail(session):
    seeded = seed_read_graph(session)
    detail = get_scan_detail(
        session, seeded["scan"].scan_id, org_id=seeded["org"].id
    )
    assert detail is not None
    return seeded, detail


@pytest.mark.parametrize("language", ["en", "pt-BR", "ru"])
def test_education_includes_zero_alert_devices_without_certifying_safety(
    administrative_session, language
):
    _, detail = _detail(administrative_session)
    detail.findings = [detail.findings[0]]
    result = build_report_education(detail, language)
    assert len(result["devices"]) == len(detail.hosts)
    clear = next(item for item in result["devices"] if not item["finding_count"])
    assert clear["status"] == "no_alerts"
    assert clear["note"] == text("device_no_alerts", language)
    assert result["hosts_without_findings"] == 1
    assert result["coverage_recorded"] is False
    assert result["evidence_completeness"] == detail.evidence_completeness


def test_cve_associations_are_grouped_by_endpoint_and_never_confirmed_by_score(
    administrative_session
):
    _, detail = _detail(administrative_session)
    first = detail.findings[0].model_copy(update={
        "source": "nmap_vulners", "cve_id": "CVE-2023-38408",
        "service": "ssh", "port": 22, "confidence": "confirmed",
    })
    second = first.model_copy(update={
        "finding_id": uuid4(), "cve_id": "CVE-2011-2523",
    })
    third = second.model_copy(update={"finding_id": uuid4(), "port": 2222})
    unassigned = first.model_copy(update={"finding_id": uuid4(), "host_ip": None})
    detail.findings = [first, second, third, unassigned]
    result = build_report_education(detail, "pt-BR")
    assert result["evidence_counts"] == {
        "correlation": 4, "observation": 0, "other": 0,
    }
    assert len(result["issue_groups"]) == 3
    assert len(result["appendix"]) == 4
    assert result["unassigned_findings"] == 1
    assert all(item["basis"] == "correlation" for item in result["appendix"])
    group = next(item for item in result["issue_groups"] if item["finding_count"] == 2)
    assert group["uncertainty"] == text("correlation_limit", "pt-BR")
    assert len(group["advisory_notes"]) == 2
    assert all(row["group"] in {g["id"] for g in result["issue_groups"]}
               for row in result["appendix"])


def test_direct_configuration_evidence_gets_specific_correction_steps(
    administrative_session
):
    _, detail = _detail(administrative_session)
    first = detail.findings[0].model_copy(update={
        "source": "nmap_nse", "source_script": "smb-protocols",
        "title": "SMBv1 protocol enabled", "port": None,
        "evidence": "SMBv1 supported", "cve_id": None,
    })
    second = first.model_copy(update={
        "finding_id": uuid4(), "source_script": "ssh-auth-methods",
        "title": "Password authentication", "evidence": "publickey password",
        "port": 22, "service": "ssh",
    })
    detail.findings = [first, second]
    result = build_report_education(detail, "pt-BR")
    assert result["evidence_counts"]["observation"] == 2
    assert {group["family"] for group in result["issue_groups"]} == {
        "smb_v1", "ssh_password",
    }
    for group in result["issue_groups"]:
        assert group["steps"] == guide(group["family"], "pt-BR")["steps"]
        assert group["recorded_observations"]
        assert group["cves"] == []


def test_shell_service_observation_does_not_manufacture_a_finding(
    administrative_session
):
    _, detail = _detail(administrative_session)
    host = next(host for host in detail.hosts if host.ports)
    host.ports[0] = host.ports[0].model_copy(update={
        "service": "bindshell", "version": "Metasploitable root shell",
    })
    detail.findings = []
    result = build_report_education(detail, "pt-BR")
    group = result["issue_groups"][0]
    assert group["basis"] == "service"
    assert group["family"] == "shell"
    assert group["finding_count"] == 0
    assert group["severity"] is None
    assert result["appendix"] == []
    assert result["affected_hosts"] == 0
    assert next(item for item in result["devices"]
                if item["address"] == str(host.ip))["status"] == "review"


def test_cached_advisories_and_scan_scoped_enrichment_are_read_only(
    administrative_session, monkeypatch
):
    seeded, _ = _detail(administrative_session)
    finding = seeded["finding"]
    finding.cve_id = "CVE-2023-38408"
    finding.source = "nmap_vulners"
    administrative_session.add(finding)
    now = datetime.now(timezone.utc)
    unrelated = make_scan(administrative_session, seeded["other_org"].id)
    administrative_session.add(NvdCacheRecord(
        query_key="cve:CVE-2023-38408", query_kind="cve",
        query_value="CVE-2023-38408", fetched_at=now,
        expires_at=now + timedelta(days=1),
        response_json={"vulnerabilities": [{"cve": {
            "id": "CVE-2023-38408", "descriptions": [{
                "lang": "en", "value": "Arbitrary code execution in ssh-agent.",
            }],
        }}]},
    ))
    for scan_id, status in (
        (seeded["scan"].scan_id, "running"),
        (seeded["scan"].scan_id, "failed"),
        (unrelated.scan_id, "pending"),
    ):
        administrative_session.add(EnrichmentJobRecord(
            scan_id=scan_id, status=status, job_type="nvd_cve",
            target_value="CVE-2023-38408",
        ))
    administrative_session.commit()
    monkeypatch.setattr("api.services.reports.get_scan_ai_analysis",
                        lambda *args, **kwargs: None)
    report = build_scan_report(
        administrative_session, seeded["scan"].scan_id,
        org_id=seeded["org"].id, kind="explained", ai_enabled=False,
        language="pt-BR",
    )
    education = report.sections
    assert education["enrichment"] == {"pending": 1, "failed": 1}
    record = next(row for row in education["appendix"]
                  if row["title"] == "CVE-2023-38408")
    assert record["advisory_effects"] == [text("code_execution", "pt-BR")]
    assert record["basis"] == "correlation"
    assert record["advisory_fetched_at"]
    assert not administrative_session.new
    assert not administrative_session.dirty


def test_service_family_uses_service_identity_instead_of_port_number():
    assert service_family(None) == "other_service"
    assert service_family("tcpwrapped") == "other_service"
    assert service_family("postgresql") == "database"


def test_exposure_review_is_explained_without_inventing_a_vulnerability(
    administrative_session
):
    _, detail = _detail(administrative_session)
    host = next(host for host in detail.hosts if host.ports)
    port = host.ports[0]
    detail.findings = []
    detail.exposures = [ExposureRead(
        exposure_id=uuid4(), scan_id=detail.scan_id, host_id=host.host_id,
        ip=host.ip, port=port.port, protocol=port.protocol,
        observed_service=port.service, role="administration", attention="review",
        confidence="medium", reason="Access needs review",
        related_finding_ids=[], detected_at=detail.timestamp,
    )]
    result = build_report_education(detail, "pt-BR")
    assert result["evidence_counts"] == {
        "correlation": 0, "observation": 0, "other": 0,
    }
    assert len(result["issue_groups"]) == 1
    group = result["issue_groups"][0]
    assert group["category"] == "service_review"
    assert group["basis"] == "service"
    assert group["finding_count"] == 0
    assert group["cves"] == []
    assert result["appendix"] == []


def test_paginated_device_chart_keeps_every_row_and_the_same_count_scale():
    rows = [(str(index), [index]) for index in range(50)]
    chart = EvidenceBars(rows, ["Records"], ["#600BB5"], 400, "Helvetica")
    first, second = chart.split(400, 160)
    assert first.rows + second.rows == rows
    assert first.maximum == second.maximum == chart.maximum == 49
    assert first.height <= 160
