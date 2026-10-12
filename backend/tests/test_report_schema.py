from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.schemas.reports import ScanReportResponse
from pydantic import ValidationError
from read_factories import seed_read_graph


def test_report_rejects_free_form_sections():
    with pytest.raises(ValidationError):
        ScanReportResponse(
            scan_id=uuid4(), kind="explained", language="en",
            generated_at=datetime.now(timezone.utc), filename="report.pdf",
            content_type="application/pdf", sections={"education": {}},
        )


def test_report_sections_match_kind_and_content_type(
    administrative_session, monkeypatch,
):
    from api.services.report_pdf import render_scan_report_pdf
    from api.services.reports import build_scan_report

    seeded = seed_read_graph(administrative_session)
    monkeypatch.setattr(
        "api.services.reports.get_scan_ai_analysis", lambda *args, **kwargs: None
    )
    report = build_scan_report(
        administrative_session, seeded["scan"].scan_id,
        org_id=seeded["org"].id, kind="explained", ai_enabled=False,
    )
    payload = report.model_dump(mode="json")
    assert ScanReportResponse.model_validate(payload).sections == report.sections
    payload["sections"]["education"] = {}
    with pytest.raises(ValidationError):
        ScanReportResponse.model_validate(payload)
    del payload["sections"]["education"]
    payload["kind"] = "technical"
    with pytest.raises(ValidationError, match="sections do not match kind"):
        ScanReportResponse.model_validate(payload)
    payload["kind"] = "explained"
    payload["content_type"] = "application/json"
    with pytest.raises(ValidationError, match="content type does not match kind"):
        ScanReportResponse.model_validate(payload)

    technical = build_scan_report(
        administrative_session, seeded["scan"].scan_id,
        org_id=seeded["org"].id, kind="technical", ai_enabled=False,
    )
    with pytest.raises(ValueError, match="technical reports are downloaded as JSON"):
        render_scan_report_pdf(technical)
