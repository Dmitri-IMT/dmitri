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
from api.services.report_education_copy import REPORT_COPY
from api.services.report_education_pdf import append_education
from api.services.report_pdf import _format_timestamp, _scan_mode_label
from read_factories import make_finding, seed_read_graph
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepTogether, Paragraph, Table


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
