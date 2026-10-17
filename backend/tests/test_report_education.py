"""Verify attribution, evidence boundaries and complete educational coverage."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from api.models.persistence import EnrichmentJobRecord, NvdCacheRecord
from api.schemas.read import ExposureRead
from api.schemas.scan import FindingEvidenceObservationPayload
from api.services.read import get_scan_detail
from api.services.report_education import (
    build_report_education,
    device_identity,
    finding_semantic_limit,
    service_family,
)
from api.services.report_education_copy import REPORT_COPY, guide, text
from api.services.report_education_pdf import EvidenceBars, append_education
from api.services.reports import build_scan_report
from read_factories import make_scan, seed_read_graph
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Table


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
        "service": "ssh", "port": 22, "confidence": "probable",
        "detection_method": "version_correlation",
        "evidence_status": "supported",
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
    assert group["uncertainty"] == text("limit_version_correlation", "pt-BR")
    assert len(group["advisory_notes"]) == 2
    assert all(row["group"] in {g["id"] for g in result["issue_groups"]}
               for row in result["appendix"])


def test_direct_configuration_evidence_gets_specific_correction_steps(
    administrative_session
):
    _, detail = _detail(administrative_session)
    smb_observation = FindingEvidenceObservationPayload(
        ip=detail.findings[0].host_ip,
        port=445,
        protocol="tcp",
        condition_key="smb:protocol:smbv1",
        method="configuration_observation",
        result="positive",
        source="nmap_nse",
        source_script="smb-protocols",
        rule_id="nse:smb-protocols",
        rule_version="1",
        evidence="SMBv1 supported",
        facts={"dialect": "SMBv1"},
    )
    first = detail.findings[0].model_copy(update={
        "source": "nmap_nse", "source_script": "smb-protocols",
        "title": "SMBv1 protocol enabled", "port": 445,
        "protocol": "tcp", "service": "microsoft-ds",
        "evidence": "SMBv1 supported", "cve_id": None,
        "detection_method": "configuration_observation",
        "evidence_status": "supported", "confidence": "confirmed",
        "evidence_observations": [smb_observation],
    })
    ssh_observation = FindingEvidenceObservationPayload(
        ip=first.host_ip,
        port=22,
        protocol="tcp",
        condition_key="title:ssh password authentication exposed",
        method="configuration_observation",
        result="positive",
        source="nmap_nse",
        source_script="ssh-auth-methods",
        rule_id="nse:ssh-auth-methods",
        rule_version="1",
        evidence="password authentication advertised",
        facts={"password_authentication": True},
    )
    second = first.model_copy(update={
        "finding_id": uuid4(), "source_script": "ssh-auth-methods",
        "title": "Password authentication", "evidence": "publickey password",
        "port": 22, "service": "ssh", "confidence": "confirmed",
        "evidence_observations": [ssh_observation],
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


@pytest.mark.parametrize(
    ("target", "method", "status", "confidence", "truncated"),
    [
        ("smb", "unknown", "unknown", None, False),
        ("smb", "configuration_observation", "inconclusive", "tentative", False),
        ("smb", "configuration_observation", "conflicting", "tentative", False),
        ("smb", "textual_reference", "inconclusive", "tentative", False),
        ("ssh", "unknown", "unknown", None, False),
        ("ssh", "configuration_observation", "inconclusive", "tentative", False),
        ("ssh", "configuration_observation", "conflicting", "tentative", False),
        ("ssh", "textual_reference", "inconclusive", "tentative", False),
    ],
)
def test_unverified_smb_and_ssh_records_do_not_get_affirmative_specific_claims(
    administrative_session, target, method, status, confidence, truncated
):
    _, detail = _detail(administrative_session)
    smb = target == "smb"
    source_script = "smb-protocols" if smb else "ssh-auth-methods"
    service = "microsoft-ds" if smb else "ssh"
    title = "SMBv1 protocol enabled" if smb else "Password authentication"
    evidence = "SMBv1 supported" if smb else "publickey password"
    port = 445 if smb else 22
    finding = detail.findings[0].model_copy(update={
        "finding_id": uuid4(),
        "source": "nmap_nse",
        "source_script": source_script,
        "title": title,
        "evidence": evidence,
        "cve_id": None,
        "service": service,
        "port": port,
        "protocol": "tcp",
        "detection_method": method,
        "evidence_status": status,
        "confidence": confidence,
        "evidence_truncated": truncated,
        "evidence_observations": [],
    })
    detail.findings = [finding]

    result = build_report_education(detail, "pt-BR")

    group = next(item for item in result["issue_groups"] if item["finding_count"])
    appendix = result["appendix"][0]
    generic_family = service_family(service)
    specific_family = "smb_v1" if smb else "ssh_password"
    assert group["family"] == generic_family
    assert group["title"] == guide(generic_family, "pt-BR")["name"]
    assert group["title"] != guide(specific_family, "pt-BR")["name"]
    assert group["meaning"] == guide(generic_family, "pt-BR")["meaning"]
    assert group["uncertainty"]
    assert appendix["semantic_limit"] == finding_semantic_limit(
        method, status, confidence, "pt-BR", evidence_truncated=truncated
    )


@pytest.mark.parametrize("target", ["smb", "ssh"])
def test_supported_direct_evidence_retains_specialized_guidance(
    administrative_session, target
):
    _, detail = _detail(administrative_session)
    smb = target == "smb"
    source_script = "smb-protocols" if smb else "ssh-auth-methods"
    service = "microsoft-ds" if smb else "ssh"
    title = "SMBv1 protocol enabled" if smb else "Password authentication"
    evidence = "SMBv1 supported" if smb else "password authentication advertised"
    port = 445 if smb else 22
    condition = "smb:protocol:smbv1" if smb else (
        "title:ssh password authentication exposed"
    )
    rule_id = "nse:smb-protocols" if smb else "nse:ssh-auth-methods"
    facts = {"dialect": "SMBv1"} if smb else {
        "password_authentication": True
    }
    observation = FindingEvidenceObservationPayload(
        ip=detail.findings[0].host_ip,
        port=port,
        protocol="tcp",
        condition_key=condition,
        method="configuration_observation",
        result="positive",
        source="nmap_nse",
        source_script=source_script,
        rule_id=rule_id,
        rule_version="1",
        evidence=evidence,
        facts=facts,
    )
    finding = detail.findings[0].model_copy(update={
        "finding_id": uuid4(),
        "source": "nmap_nse",
        "source_script": source_script,
        "title": title,
        "evidence": evidence,
        "cve_id": None,
        "service": service,
        "port": port,
        "protocol": "tcp",
        "detection_method": "configuration_observation",
        "evidence_status": "supported",
        "confidence": "confirmed",
        "evidence_truncated": False,
        "evidence_observations": [observation],
    })
    detail.findings = [finding]

    result = build_report_education(detail, "pt-BR")

    group = next(item for item in result["issue_groups"] if item["finding_count"])
    appendix = result["appendix"][0]
    specific_family = "smb_v1" if smb else "ssh_password"
    assert group["family"] == specific_family
    assert group["title"] == guide(specific_family, "pt-BR")["name"]
    assert group["meaning"] == guide(specific_family, "pt-BR")["meaning"]
    assert group["steps"] == guide(specific_family, "pt-BR")["steps"]
    assert appendix["semantic_limit"] is None


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


def test_education_v3_keeps_semantically_distinct_records_and_limits_per_group(
    administrative_session,
):
    _, detail = _detail(administrative_session)
    base = detail.findings[0].model_copy(update={
        "source": "nmap_vulners",
        "cve_id": "CVE-2023-38408",
        "service": "ssh",
        "port": 22,
        "detection_method": "version_correlation",
        "evidence_status": "supported",
        "confidence": "probable",
        "evidence_truncated": False,
        "evidence_observations": [],
    })
    stronger_but_different = base.model_copy(update={
        "finding_id": uuid4(),
        "detection_method": "specific_check",
        "evidence_status": "inconclusive",
        "confidence": "tentative",
        "evidence_truncated": True,
    })
    detail.findings = [base, stronger_but_different]
    detail.evidence_summary = None

    result = build_report_education(detail, "en")

    assert result["version"] == "3"
    assert result["evidence_counts"] == {
        "observation": 0,
        "correlation": 2,
        "other": 0,
    }
    assert result["evidence_summary"]["total_records"] == 2
    assert result["evidence_summary"]["by_method"] == {
        "version_correlation": 1,
        "configuration_observation": 0,
        "specific_check": 1,
        "textual_reference": 0,
        "unknown": 0,
    }
    assert len(result["issue_groups"]) == 2
    assert len(result["appendix"]) == 2
    for finding in (base, stronger_but_different):
        row = next(
            item for item in result["appendix"]
            if item["finding_id"] == str(finding.finding_id)
        )
        group = next(
            item for item in result["issue_groups"] if item["id"] == row["group"]
        )
        for item in (row, group):
            assert item["detection_method"] == finding.detection_method
            assert item["evidence_status"] == finding.evidence_status
            assert item["confidence"] == finding.confidence
            assert item["evidence_truncated"] is finding.evidence_truncated


@pytest.mark.parametrize("language", ["en", "pt-BR", "ru"])
def test_supported_specific_check_limit_is_localized_and_scoped(
    administrative_session, language
):
    _, detail = _detail(administrative_session)
    endpoint = str(detail.findings[0].host_ip)
    observation = FindingEvidenceObservationPayload(
        ip=endpoint,
        port=443,
        protocol="tcp",
        condition_key="tls:protocol:tls1.0",
        method="specific_check",
        result="positive",
        source="testssl.sh",
        source_script="protocols",
        rule_id="testssl:tls1.0",
        rule_version="1",
        evidence="TLS 1.0 accepted by the tested endpoint",
        facts={"protocol": "TLS 1.0"},
    )
    finding = detail.findings[0].model_copy(update={
        "finding_id": uuid4(),
        "source": "testssl.sh",
        "source_script": "protocols",
        "title": "TLS 1.0 accepted",
        "service": "https",
        "port": 443,
        "protocol": "tcp",
        "detection_method": "specific_check",
        "evidence_status": "supported",
        "confidence": "confirmed",
        "evidence_truncated": False,
        "evidence_observations": [observation],
    })
    detail.findings = [finding]

    result = build_report_education(detail, language)

    appendix = result["appendix"][0]
    group = result["issue_groups"][0]
    limit = text("limit_specific_check", language)
    assert appendix["semantic_limit"] == limit
    assert group["uncertainty"] == limit
    assert appendix["evidence_observations"][0]["ip"] == endpoint
    assert appendix["evidence_observations"][0]["port"] == 443
    assert appendix["evidence_observations"][0]["condition_key"] == (
        "tls:protocol:tls1.0"
    )


def test_standalone_checks_are_limited_coverage_not_finding_totals(
    administrative_session,
):
    _, detail = _detail(administrative_session)
    detail.findings = [detail.findings[0].model_copy(update={
        "source": "nmap_nse",
        "cve_id": None,
    })]
    detail.evidence_summary = None
    detail.finding_observations = [FindingEvidenceObservationPayload(
        ip="192.168.1.10",
        port=445,
        protocol="tcp",
        condition_key="SMBv1 availability",
        method="configuration_observation",
        result="negative",
        source="nmap_nse",
        source_script="smb-protocols",
        rule_id="smb:smbv1",
        rule_version="1",
        evidence="SMBv1 not offered",
    )]
    detail.finding_observations_truncated = True

    result = build_report_education(detail, "pt-BR")

    assert result["version"] == "3"
    assert result["evidence_summary"]["total_records"] == 1
    assert result["evidence_counts"] == {
        "observation": 1,
        "correlation": 0,
        "other": 0,
    }
    assert len(result["appendix"]) == 1
    assert result["finding_observations_truncated"] is True
    assert result["finding_observations"] == [
        detail.finding_observations[0].model_dump(mode="json")
    ]


@pytest.mark.parametrize("language", ["en", "pt-BR", "ru"])
def test_evidence_report_copy_is_localized_for_pdf_labels(language):
    translated = [
        text("method_version_correlation", language),
        text("status_supported_version", language),
        text("confidence_probable", language),
        text("evidence_truncated", language),
        text("standalone_observations_title", language),
        text("observation_scope_note", language),
    ]
    assert all(translated)
    assert len(set(translated)) == len(translated)


def test_pdf_appendix_keeps_semantic_limit_separate_from_truncation(
    administrative_session, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    finding.source = "nmap_nse"
    finding.source_script = "smb-protocols"
    finding.title = "SMBv1 protocol enabled"
    finding.evidence = "SMBv1 supported"
    finding.finding_evidence_policy_version = "1"
    finding.evidence_observations_json = []
    finding.evidence_truncated = True
    administrative_session.add(finding)
    administrative_session.commit()
    monkeypatch.setattr(
        "api.services.reports.get_scan_ai_analysis",
        lambda *args, **kwargs: None,
    )

    report = build_scan_report(
        administrative_session,
        seeded["scan"].scan_id,
        org_id=seeded["org"].id,
        kind="explained",
        ai_enabled=False,
        language="pt-BR",
    )
    education = report.sections
    record = next(
        item for item in education["appendix"]
        if item["finding_id"] == str(finding.finding_id)
    )
    styles = getSampleStyleSheet()
    for name, base in (
        ("ReportBody", "BodyText"),
        ("ReportHeading", "Heading2"),
        ("ReportChapter", "Heading2"),
        ("ReportDevice", "Heading2"),
        ("ReportCard", "BodyText"),
        ("ReportSmall", "BodyText"),
    ):
        styles.add(ParagraphStyle(name, parent=styles[base]))
    story = []
    append_education(
        story, report.sections, styles, REPORT_COPY["pt-BR"], "pt-BR", 500, "Helvetica"
    )
    appendix_table = next(
        item for item in story
        if isinstance(item, Table)
        and len(item._cellvalues) > 1
        and item._cellvalues[0][1].getPlainText() == "CVE / Gxx"
    )
    identity = appendix_table._cellvalues[1][1].getPlainText()

    assert record["semantic_limit"]
    assert record["semantic_limit"] in identity
    assert text("evidence_truncated", "pt-BR") in identity
    assert identity.count(text("limit", "pt-BR")) == 2


def test_paginated_device_chart_keeps_every_row_and_the_same_count_scale():
    rows = [(str(index), [index]) for index in range(50)]
    chart = EvidenceBars(rows, ["Records"], ["#600BB5"], 400, "Helvetica")
    first, second = chart.split(400, 160)
    assert first.rows + second.rows == rows
    assert first.maximum == second.maximum == chart.maximum == 49
    assert first.height <= 160
