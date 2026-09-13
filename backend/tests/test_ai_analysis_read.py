from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from api.core.config import get_settings
from api.main import app
from api.models.persistence import AIScanAnalysisRecord
from api.schemas.ai import ScanAIAnalysis
from api.services.ai.jobs import (
    AIAnalysisAlreadyRequestedError,
    request_scan_ai_analysis,
)
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
        "status": "unavailable",
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


def test_analysis_read_returns_not_requested_without_triggering_generation(
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
    assert response.json() == {
        "scan_id": str(seeded["scan"].scan_id),
        "status": "not_requested",
    }
    count = administrative_session.exec(
        select(func.count()).select_from(AIScanAnalysisRecord)
    ).one()
    assert count == 0


def test_analysis_request_creates_one_pending_job(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)
    url = f"/api/v1/scans/{seeded['scan'].scan_id}/analysis"
    headers = bearer_headers(seeded["org"].id, "viewer")

    response = client.post(url, headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.scan_id == seeded["scan"].scan_id
    assert record.status == "pending"

    repeated = client.post(url, headers=headers)
    assert repeated.status_code == 409
    administrative_session.refresh(record)
    assert record.status == "pending"
    assert record.attempts == 0


@pytest.mark.parametrize("status", ["processing", "completed"])
def test_analysis_request_conflicts_after_processing_or_completion(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
    status,
):
    seeded = seed_read_graph(administrative_session)
    analysis = _analysis()
    record = AIScanAnalysisRecord(
        scan_id=seeded["scan"].scan_id,
        provider="fake",
        model="fake-v1",
        status=status,
        analysis_json=(
            analysis.model_dump(mode="json") if status == "completed" else None
        ),
        context_version="1",
        prompt_version="1",
        completed_at=datetime.now(timezone.utc) if status == "completed" else None,
    )
    administrative_session.add(record)
    administrative_session.commit()

    response = client.post(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 409
    administrative_session.refresh(record)
    assert record.status == status
    assert record.analysis_json == (
        analysis.model_dump(mode="json") if status == "completed" else None
    )


def test_concurrent_analysis_requests_create_one_job(administrative_session):
    seeded = seed_read_graph(administrative_session)
    barrier = Barrier(2)
    engine = administrative_session.get_bind()

    class RacingSession(type(administrative_session)):
        def commit(self):
            barrier.wait(timeout=5)
            super().commit()

    def request():
        with RacingSession(engine) as session:
            try:
                response = request_scan_ai_analysis(
                    session,
                    seeded["scan"].scan_id,
                    org_id=seeded["org"].id,
                    ai_enabled=True,
                    provider_name="fake",
                    model="fake-v1",
                )
            except AIAnalysisAlreadyRequestedError:
                return "conflict"
            assert response is not None
            return response.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: request(), range(2)))

    assert sorted(outcomes) == ["conflict", "pending"]
    administrative_session.expire_all()
    records = administrative_session.exec(select(AIScanAnalysisRecord)).all()
    assert len(records) == 1
    assert records[0].scan_id == seeded["scan"].scan_id


def test_analysis_request_retries_failed_job(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)
    record = AIScanAnalysisRecord(
        scan_id=seeded["scan"].scan_id,
        provider="fake",
        model="fake-v1",
        status="failed",
        context_version="1",
        prompt_version="1",
        attempts=2,
        last_error="provider_timeout",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    administrative_session.add(record)
    administrative_session.commit()

    response = client.post(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    administrative_session.refresh(record)
    assert record.status == "pending"
    assert record.attempts == 0
    assert record.last_error is None
    assert record.started_at is None
    assert record.completed_at is None


def test_analysis_request_hides_foreign_scan(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)

    response = client.post(
        f"/api/v1/scans/{seeded['foreign_scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 404
    assert administrative_session.exec(select(AIScanAnalysisRecord)).all() == []


def test_analysis_request_is_unavailable_when_ai_is_disabled(
    client,
    administrative_session,
    bearer_headers,
):
    seeded = seed_read_graph(administrative_session)

    response = client.post(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "unavailable"
    assert administrative_session.exec(select(AIScanAnalysisRecord)).all() == []


def test_analysis_request_is_unavailable_before_scan_completion(
    client,
    administrative_session,
    bearer_headers,
    enable_ai,
):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].status = "running"
    administrative_session.add(seeded["scan"])
    administrative_session.commit()

    response = client.post(
        f"/api/v1/scans/{seeded['scan'].scan_id}/analysis",
        headers=bearer_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "unavailable"
    assert administrative_session.exec(select(AIScanAnalysisRecord)).all() == []


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
        completed_at=datetime.now(timezone.utc) if status == "failed" else None,
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
    assert "analysis" not in body
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
