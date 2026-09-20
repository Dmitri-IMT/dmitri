from __future__ import annotations

from read_factories import seed_read_graph


def test_explained_report_is_available_without_ai_analysis(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/reports/explained",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

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
