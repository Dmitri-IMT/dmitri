from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.models.persistence import RiskSnapshotRecord
from api.schemas.ai import (
    AIFindingExplanation,
    ScanAIAnalysis,
    ScanAIAnalysisCompleted,
)
from api.services.report_pdf import _COPY, _format_timestamp, _scan_mode_label
from read_factories import make_finding, seed_read_graph


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
    assert body["sections"]["attention_level"] in {
        "none",
        "low",
        "medium",
        "high",
        "critical",
    }
    assert body["sections"]["what_to_do_first"]
    sections = body["sections"]
    assert sections["metrics"] == {
        "hosts_scanned": 2,
        "finding_records": 2,
        "unique_cve_ids": 0,
        "open_ports": 1,
    }
    assert sections["severity_counts"] == {
        "critical": 0,
        "high": 1,
        "medium": 0,
        "low": 1,
    }
    assert sections["top_hosts"][0] == {
        "hostname": "host-a",
        "address": "192.168.1.10",
        "findings": 1,
    }
    assert sections["important_findings"][0]["recommendation"] == "Patch it."
    assert {
        action["title"]: action["priority"]
        for action in sections["what_to_do_first"]
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
    assert [_COPY[language]["ports"] for language in ("en", "pt-BR", "ru")] == [
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
    findings = response.json()["sections"]["important_findings"]
    finding = next(
        item
        for item in findings
        if item["title"] == seeded["finding"].title
    )
    assert finding["recommendation"] == "Replace it with a modern, supported setting."


def test_explained_report_includes_a_finding_at_the_attention_level(
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
    assert sections["attention_level"] == "critical"
    assert len(sections["important_findings"]) == 5
    assert any(
        finding["title"] == "Critical attention finding"
        for finding in sections["important_findings"]
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
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment; filename=\"dmitri-scan-" in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF-")
    assert response.headers["content-disposition"].endswith('.pdf"')


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
