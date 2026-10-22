from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.models.persistence import (
    IndustrialServiceRecord,
    PortRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
    ServiceRecord,
)
from api.schemas.ai import (
    AIFindingExplanation,
    ScanAIAnalysis,
    ScanAIAnalysisCompleted,
)
from api.services.report_education_copy import REPORT_COPY
from api.services.report_education_pdf import append_education
from api.services.report_pdf import _format_timestamp, _scan_mode_label
from read_factories import make_finding, seed_read_graph
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepTogether, Paragraph, Table
from sqlmodel import select


def _add_dual_protocol_observations(session, seeded):
    host = session.exec(select(ScanHostRecord).where(
        ScanHostRecord.scan_id == seeded["scan"].scan_id,
        ScanHostRecord.ip == "192.168.1.10",
    )).one()
    session.add(IndustrialServiceRecord(
        scan_host_id=host.id, protocol="modbus_tcp", port=502,
        confidence="confirmed", evidence_sources_json=["modbus_response"],
    ))
    phase = {"status": "completed", "reason_codes": [], "truncated": False,
             "observed_at": datetime.now(timezone.utc).isoformat()}
    observation = {
        "schema_version": 1, "inventory_phase": phase,
        "identity": {"application_uri": "urn:UA_NODE_SENTINEL",
                     "product_uri": "UA_PRODUCT_SENTINEL",
                     "application_name": "UA_METADATA_SENTINEL",
                     "application_type": "Server"},
        "certificate_sha256": "a" * 64,
        "endpoints": [{
            "endpoint_url": "opc.tcp://u:SECRET_SENTINEL@192.168.1.10:4840/SECRET_PATH",
            "security_policy_uri": "POLICY_SENTINEL",
            "security_mode": "None",
            "transport_profile_uri": "PROFILE_SENTINEL",
            "security_level": 0,
            "user_token_count": 1,
            "user_token_types": ["Anonymous"],
            "target_matches": True,
        }],
        "mapping": {"phase": phase, "nodes": [{"node_id": "NODE_SENTINEL",
                    "parent_node_id": None, "depth": 0, "node_class": "Variable",
                    "browse_name": "NODE_METADATA_SENTINEL",
                    "display_name": "DISPLAY_SENTINEL",
                    "data_type": "TYPE_SENTINEL", "value_rank": -1, "access_level": 3,
                    "user_access_level": 3, "value_read_status": "Good"}],
                    "references": [], "references_observed": 0,
                    "value_reads_attempted": 1,
                    "selected_endpoint_index": 0, "anonymous_session_activated": True,
                    "browse_succeeded": True, "application_value_read_succeeded": True,
                    "value_good_count": 1,
                    "security_mode": {
                        "value": "None", "source": "get_endpoints", "status": "Good",
                    },
                    "security_policy": {
                        "value": "None", "source": "get_endpoints", "status": "Good",
                    }},
    }
    session.add(IndustrialServiceRecord(
        scan_host_id=host.id, protocol="opcua_tcp", port=4840,
        confidence="confirmed", evidence_sources_json=["valid_opcua_response"],
        opcua_observation_json=observation,
    ))
    announced_only = {**observation, "mapping": None}
    session.add(IndustrialServiceRecord(
        scan_host_id=host.id, protocol="opcua_tcp", port=4841,
        confidence="confirmed", evidence_sources_json=["valid_opcua_response"],
        opcua_observation_json=announced_only,
    ))
    ua_port = PortRecord(scan_host_id=host.id, port=4840, protocol="tcp", state="open")
    session.add(ua_port)
    session.flush()
    session.add(ServiceRecord(port_id=ua_port.id, name="opcua",
                              version="BANNER_SECRET_SENTINEL"))
    session.commit()


def test_mixed_protocol_reports_aggregate_and_redact_opcua_payload(
    client, administrative_session, bearer_headers, tmp_path,
):
    seeded = seed_read_graph(administrative_session)
    _add_dual_protocol_observations(administrative_session, seeded)

    technical = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/technical",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert technical.status_code == 200
    exported = technical.json()["sections"]
    assert exported["industrial_protocols"]["modbus_tcp"]["service_count"] == 1
    modbus = exported["industrial_protocols"]["modbus_tcp"]
    assert (modbus["mapping_completed"] + modbus["mapping_limited"]
            + modbus["mapping_not_attempted"] == modbus["service_count"])
    ua = exported["industrial_protocols"]["opcua_tcp"]
    assert ua["service_count"] == ua["confirmed_services"] == 2
    assert ua["mapping_not_attempted"] == 1
    assert ua["anonymous_read_verified"] == 1
    assert exported["scan"]["findings"]
    serialized = technical.text
    for sentinel in (
        "NODE_SENTINEL", "SECRET_SENTINEL", "UA_NODE_SENTINEL",
        "UA_PRODUCT_SENTINEL", "UA_METADATA_SENTINEL", "a" * 64,
        "NODE_METADATA_SENTINEL", "DISPLAY_SENTINEL", "TYPE_SENTINEL",
        "BANNER_SECRET_SENTINEL", "POLICY_SENTINEL", "PROFILE_SENTINEL",
    ):
        assert sentinel not in serialized
    port = next(item for host in exported["scan"]["hosts"] for item in host["ports"]
                if item["port"] == 4840)
    assert port["service"] == "opcua"
    assert port["version"] is None
    ua_service = next(item for host in exported["scan"]["hosts"]
                      for item in host["industrial_services"]
                      if item["protocol"] == "opcua_tcp")
    assert ua_service["observation"] is None

    explained = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained",
        params={"language": "en"},
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert explained.status_code == 200
    education = explained.json()["sections"]
    assert education["industrial_protocols"] == exported["industrial_protocols"]
    ua_device_service = next(
        item for device in education["devices"] for item in device["services"]
        if item["port"] == 4840
    )
    assert ua_device_service["service"] == "opcua"
    assert ua_device_service["version"] is None
    styles = {name: ParagraphStyle(name, fontName="Helvetica", fontSize=9)
              for name in ("ReportBody", "ReportHeading", "ReportChapter",
                           "ReportCard", "ReportSmall", "ReportDevice")}
    story: list[object] = []
    append_education(
        story, education, styles, REPORT_COPY["en"], "en", 460, "Helvetica"
    )
    pdf_text = "\n".join(line for item in story for line in _flowable_text(item))
    assert "Industrial services by protocol" in pdf_text
    assert "OPC UA" in pdf_text and "Modbus TCP" in pdf_text
    assert "anonymous reads verified: 1" in pdf_text
    for sentinel in (
        "BANNER_SECRET_SENTINEL", "NODE_SENTINEL", "SECRET_SENTINEL",
        "UA_NODE_SENTINEL", "UA_METADATA_SENTINEL", "POLICY_SENTINEL",
        "PROFILE_SENTINEL", "DISPLAY_SENTINEL", "TYPE_SENTINEL", "a" * 64,
    ):
        assert sentinel not in pdf_text

    pdf_response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained/download",
        params={"language": "en"},
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-")
    assert b"BANNER_SECRET_SENTINEL" not in pdf_response.content
    pdf_path = tmp_path / "dmitri-task7-explained.pdf"
    pdf_path.write_bytes(pdf_response.content)


def test_explained_report_is_available_without_ai_analysis(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    responses = {
        language: client.get(
            f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained",
            params={"language": language},
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
        for language in ("en", "pt-BR", "ru")
    }
    response = responses["en"]

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "explained"
    assert body["scan_id"] == str(seeded["scan"].scan_id)
    sections = body["sections"]
    assert sections["actions"]
    assert {"education", "metrics", "top_hosts", "important_findings",
            "what_to_do_first"}.isdisjoint(sections)
    assert len(sections["devices"]) == 2
    assert len(sections["appendix"]) == 2
    assert sum(device["open_ports"] for device in sections["devices"]) == 1
    assert sections["severity_counts"] == {
        "critical": 0,
        "high": 1,
        "medium": 0,
        "low": 1,
    }
    assert sections["devices"][0]["hostname"] == "host-a"
    assert sections["appendix"][0]["recommendation"] == "Patch it."
    assert {
        action["title"]: action["priority"]
        for action in sections["actions"]
    } == {"Vulnerable service": "high", "Weak cipher": "low"}
    assert sections["method"]
    assert sections["limitations"]
    assert sections["scope"] == seeded["scan"].subnet
    assert sections["scan_mode"] == "quick"
    assert sections["scan_timestamp"].startswith(
        seeded["scan"].timestamp.strftime("%Y-%m-%dT%H:%M")
    )
    assert "finding records" in responses["en"].json()["sections"]["overview"]
    assert "registros de achados" in responses["pt-BR"].json()["sections"]["overview"]
    assert "записей о находках" in responses["ru"].json()["sections"]["overview"]
    assert _scan_mode_label("quick", "en") == "Quick (basic port checks)"
    assert _scan_mode_label("quick", "pt-BR") == "Rápida (verificação básica de portas)"
    assert _scan_mode_label("quick", "ru") == "Быстрое (базовая проверка портов)"
    assert [REPORT_COPY[language]["ports"] for language in ("en", "pt-BR", "ru")] == [
        "Open ports",
        "Portas abertas",
        "Открытые порты",
    ]
    expected_timestamp = seeded["scan"].timestamp.strftime("%d/%m/%Y %H:%M UTC")
    assert _format_timestamp(seeded["scan"].timestamp) == expected_timestamp


def test_explained_report_uses_ai_recommendation_for_finding(
    client,
    administrative_session,
    bearer_headers,
    monkeypatch,
):
    seeded = seed_read_graph(administrative_session)
    now = datetime.now(timezone.utc)
    completed = ScanAIAnalysisCompleted(
        scan_id=seeded["scan"].scan_id,
        analysis_id=uuid4(),
        provider="groq",
        model="test-model",
        language="en",
        context_version="test-v1",
        prompt_version="test-v1",
        created_at=now,
        updated_at=now,
        completed_at=now,
        status="completed",
        analysis=ScanAIAnalysis(
            executive_summary="A clear executive summary.",
            overall_assessment="A clear overall assessment.",
            plain_language_summary="A clear plain language summary.",
            priority_actions=[],
            important_findings=[
                AIFindingExplanation(
                    finding_id=seeded["finding"].finding_id,
                    why_it_matters="This setting may expose the device.",
                    plain_language_explanation="The service uses a weak setting.",
                    recommendation="Replace it with a modern, supported setting.",
                    evidence_used=["Observed service banner."],
                    uncertainty=None,
                )
            ],
            uncertainties=[],
        ),
    )
    monkeypatch.setattr(
        "api.services.reports.get_scan_ai_analysis",
        lambda *args, **kwargs: completed,
    )

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    findings = response.json()["sections"]["appendix"]
    finding = next(
        item
        for item in findings
        if item["title"] == seeded["finding"].title
    )
    assert finding["recommendation"] == "Replace it with a modern, supported setting."


def test_explained_report_register_includes_all_findings_regardless_of_rank(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)
    high_findings = [
        make_finding(
            administrative_session,
            seeded["scan"].scan_id,
            seeded["scan_host"].id,
            f"high-score-{index}",
            severity="high",
        )
        for index in range(5)
    ]
    for index, finding in enumerate(high_findings):
        finding.title = f"High score finding {index}"
        administrative_session.add(finding)
    critical = make_finding(
        administrative_session,
        seeded["scan"].scan_id,
        seeded["scan_host"].id,
        "critical-lower-score",
        severity="critical",
    )
    critical.title = "Critical attention finding"
    administrative_session.add(critical)
    for finding, score in [*((item, 100.0) for item in high_findings), (critical, 0.0)]:
        administrative_session.add(
            RiskSnapshotRecord(
                finding_id=finding.id,
                confidence="confirmed",
                exploitability=0.0,
                risk_score=score,
                rationale="test ranking",
            )
        )
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    sections = response.json()["sections"]
    assert sections["severity_counts"]["critical"] == 1
    assert len(sections["appendix"]) == 8
    assert any(
        finding["title"] == "Critical attention finding"
        for finding in sections["appendix"]
    )


def test_technical_report_download_has_attachment_header(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/technical/download",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment; filename=\"dmitri-scan-" in response.headers[
        "content-disposition"
    ]
    assert response.headers["content-disposition"].endswith('.json"')
    payload = response.json()
    assert payload["kind"] == "technical"
    assert payload["content_type"] == "application/json"
    assert payload["sections"]["scan"]["scan_id"] == str(seeded["scan"].scan_id)


def test_technical_report_preview_returns_downloadable_json_shape(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/technical",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"].endswith("-technical.json")
    assert payload["content_type"] == "application/json"
    assert payload["sections"]["scan"]["scan_id"] == str(seeded["scan"].scan_id)


def test_technical_report_preserves_evidence_observations_and_policy_fields(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)
    scan = seeded["scan"]
    finding = seeded["finding"]
    standalone = {
        "ip": "192.168.1.10",
        "port": 445,
        "protocol": "tcp",
        "unit_id": None,
        "condition_key": "SMBv1 availability",
        "method": "configuration_observation",
        "result": "negative",
        "source": "nmap_nse",
        "source_script": "smb-protocols",
        "rule_id": "smb:smbv1",
        "rule_version": "1",
        "evidence": "SMBv1 not offered",
        "facts": {"dialect": "SMBv2"},
    }
    associated = {
        "ip": "192.168.1.10",
        "port": 80,
        "protocol": "tcp",
        "unit_id": None,
        "condition_key": "CVE-2023-38408",
        "method": "version_correlation",
        "result": "positive",
        "source": "nmap_vulners",
        "source_script": None,
        "rule_id": "catalog:nmap-vulners",
        "rule_version": "1",
        "evidence": "Observed package version matched the advisory range",
        "facts": {
            "product": "openssh",
            "version": "9.2p1",
            "cve_id": "CVE-2023-38408",
        },
    }
    scan.finding_evidence_policy_version = "1"
    scan.finding_observations_json = [standalone]
    scan.finding_observations_truncated = True
    finding.source = "nmap_vulners"
    finding.cve_id = "CVE-2023-38408"
    finding.finding_evidence_policy_version = "1"
    finding.evidence_observations_json = [associated]
    finding.evidence_truncated = True
    finding.confidence = "probable"
    administrative_session.add(scan)
    administrative_session.add(finding)
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{scan.scan_id}/reports/technical",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    payload = response.json()["sections"]["scan"]
    assert payload["finding_evidence_policy_version"] == "1"
    assert payload["finding_observations"] == [standalone]
    assert payload["finding_observations_truncated"] is True
    exported = next(
        item for item in payload["findings"]
        if item["finding_id"] == str(finding.finding_id)
    )
    assert exported["evidence_observations"] == [associated]
    assert exported["evidence_truncated"] is True
    assert exported["detection_method"] == "version_correlation"
    assert exported["evidence_status"] == "inconclusive"
    assert exported["confidence"] == "probable"


@pytest.mark.parametrize("language", ["pt-BR", "en", "ru"])
def test_explained_report_download_renders_long_escaped_details(
    client,
    administrative_session,
    bearer_headers,
    language,
):
    seeded = seed_read_graph(administrative_session)
    seeded["finding"].description = "<script> & detalhes técnicos " * 120
    seeded["finding"].recommendation = "Ajustar <configuração> & revisar. " * 80
    seeded["finding"].evidence = "Banner observado: <texto> & resposta. " * 120
    administrative_session.add(seeded["finding"])
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained/download",
        params={"language": language},
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 5_000


def _flowable_text(flowable: object) -> list[str]:
    if isinstance(flowable, Paragraph):
        return [flowable.getPlainText()]
    if isinstance(flowable, KeepTogether):
        return [
            line
            for child in flowable._content
            for line in _flowable_text(child)
        ]
    if isinstance(flowable, Table):
        lines: list[str] = []
        for row in flowable._cellvalues:
            for cell in row:
                if isinstance(cell, list):
                    for child in cell:
                        lines.extend(_flowable_text(child))
                else:
                    lines.extend(_flowable_text(cell))
        return lines
    return []


def test_explained_report_download_includes_priorities_without_ai(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained",
        params={"language": "en"},
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    sections = response.json()["sections"]
    styles = {
        name: ParagraphStyle(name, fontName="Helvetica", fontSize=9)
        for name in (
            "ReportBody",
            "ReportHeading",
            "ReportChapter",
            "ReportCard",
            "ReportSmall",
            "ReportDevice",
        )
    }
    story: list[object] = []
    append_education(story, sections, styles, REPORT_COPY["en"], "en", 460, "Helvetica")
    text = "\n".join(line for item in story for line in _flowable_text(item))
    assert "Recommended priorities" in text
    assert "High: Vulnerable service" in text
    assert "Low: Weak cipher" in text
