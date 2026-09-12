from datetime import datetime, timezone

import pytest
from api.core.config import get_settings
from api.main import app
from api.models.persistence import AIScanAnalysisRecord
from api.services.ai.schemas import ScanAIAnalysis
from pydantic import SecretStr
from read_factories import seed_read_graph
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select


def _analysis() -> ScanAIAnalysis:
    return ScanAIAnalysis(
        executive_summary="One issue needs attention.",
        overall_assessment="The scan has a limited but important risk.",
        plain_language_summary="One network service should be reviewed.",
        priority_actions=[],
        important_findings=[],
        uncertainties=[],
    )


@pytest.fixture
def enable_ai():
    settings = get_settings().model_copy(
        update={"ai_enabled": True, "ai_api_key": SecretStr("fake-key")}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_analysis_read_is_unavailable_when_ai_is_disabled(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "scan_id": str(seeded["scan"].scan_id),
        "analysis_id": None,
        "status": "unavailable",
        "analysis": None,
        "provider": None,
        "model": None,
        "context_version": None,
        "prompt_version": None,
        "created_at": None,
        "updated_at": None,
        "completed_at": None,
    }


def test_analysis_read_is_unavailable_without_api_key(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)
    settings = get_settings().model_copy(
        update={"ai_enabled": True, "ai_api_key": None}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = client.get(
            f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_analysis_read_returns_pending_without_triggering_generation(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["analysis"] is None
    count = administrative_session.exec(
        select(func.count()).select_from(AIScanAnalysisRecord)
    ).one()
    assert count == 0


@pytest.mark.parametrize("status", ["pending", "processing", "failed"])
def test_analysis_read_returns_persisted_non_completed_status(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
    status,
):
    seeded = seed_read_graph(administrative_session)
    record = AIScanAnalysisRecord(
        scan_id=seeded["scan"].scan_id,
        provider="fake",
        model="fake-v1",
        status=status,
        context_version="1",
        prompt_version="1",
    )
    administrative_session.add(record)
    administrative_session.commit()
    administrative_session.refresh(record)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == status
    assert body["analysis"] is None
    assert body["analysis_id"] == str(record.analysis_id)
    assert body["provider"] == "fake"
    assert body["model"] == "fake-v1"


def test_analysis_read_returns_validated_completed_payload(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)
    completed_at = datetime.now(timezone.utc)
    analysis = _analysis()
    record = AIScanAnalysisRecord(
        scan_id=seeded["scan"].scan_id,
        provider="fake",
        model="fake-v1",
        status="completed",
        analysis_json=analysis.model_dump(mode="json"),
        context_version="1",
        prompt_version="1",
        completed_at=completed_at,
    )
    administrative_session.add(record)
    administrative_session.commit()
    administrative_session.refresh(record)

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["analysis"] == analysis.model_dump(mode="json")
    assert body["completed_at"] == completed_at.isoformat().replace("+00:00", "Z")


def test_analysis_read_hides_foreign_scan_even_when_ai_is_disabled(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.get(
        f"/api/v1/scans/{seeded['foreign_scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_analysis_read_is_unavailable_for_failed_scan(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].status = "failed"
    administrative_session.add(seeded["scan"])
    administrative_session.commit()

    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_ai_analysis_storage_rejects_more_than_one_record_per_scan(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    common = {
        "scan_id": seeded["scan"].scan_id,
        "provider": "fake",
        "model": "fake-v1",
        "context_version": "1",
        "prompt_version": "1",
    }
    administrative_session.add(AIScanAnalysisRecord(**common))
    administrative_session.commit()
    administrative_session.add(AIScanAnalysisRecord(**common))

    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_ai_analysis_storage_rejects_completed_record_without_payload(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    administrative_session.add(
        AIScanAnalysisRecord(
            scan_id=seeded["scan"].scan_id,
            provider="fake",
            model="fake-v1",
            status="completed",
            context_version="1",
            prompt_version="1",
        )
    )

    with pytest.raises(IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()
