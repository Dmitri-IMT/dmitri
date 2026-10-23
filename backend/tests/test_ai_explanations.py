from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.core.config import get_settings
from api.main import app
from api.models.persistence import (
    AIExplanationRecord,
    AIUsageRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.schemas.ai import ExplanationPoint, MachineExplanation, ScanExplanation
from api.services.ai.openai_responses import AIProviderError, ProviderUsageEvent
from read_factories import seed_read_graph
from sqlmodel import select


class ExplanationProvider:
    def __init__(self):
        self.calls = []
        self.defect = None

    def explain_context(self, context, *, scope, language):
        self.calls.append((context, scope, language))
        if self.defect == "failure":
            raise AIProviderError("provider_timeout", retryable=True)
        if scope == "host":
            return MachineExplanation(
                what_it_is="The scan could not identify its type.",
                problems="Its software has a known problem.",
            )
        lead = context["allowed_leads"][0]
        return ScanExplanation(
            in_short=(
                "Check machine_999 first." if self.defect == "reference"
                else "Check the to-do list for the affected machines."
            ),
            meanings=[ExplanationPoint(
                lead="999 critical problems." if self.defect == "count" else lead,
                text="Ask your IT person to check these.",
            )],
            not_seen=["Passwords and online accounts were not checked."],
        )

    def drain_usage_events(self):
        return [ProviderUsageEvent(
            f"explain_{self.calls[-1][1]}", "test", "success", input_tokens=10,
        )]


@pytest.fixture
def provider(monkeypatch):
    settings = get_settings().model_copy(update={
        "ai_enabled": True, "ai_api_key": "test-key", "ai_chat_daily_limit": 2,
    })
    app.dependency_overrides[get_settings] = lambda: settings
    result = ExplanationProvider()
    monkeypatch.setattr("api.routers.ai.build_ai_provider", lambda settings: result)
    yield result
    app.dependency_overrides.pop(get_settings, None)


def ask(client, seeded, actor_headers, scope="scan", language="en", org_id=None):
    context_id = seeded["scan"].scan_id if scope == "scan" else seeded["host"].id
    key = str(org_id or seeded["org"].id)
    headers = seeded.setdefault("headers", {})
    if key not in headers:
        headers[key] = actor_headers(org_id or seeded["org"].id, "viewer")
    return client.post(
        "/api/v1/ai/explain",
        json={"scope": scope, "context_id": str(context_id), "language": language},
        headers=headers[key],
    )


def test_cache_language_and_anonymous_inputs(
    client, administrative_session, actor_headers, provider,
):
    seeded = seed_read_graph(administrative_session)
    first = ask(client, seeded, actor_headers)
    assert first.status_code == 200, first.text
    assert ask(client, seeded, actor_headers).json() == first.json()
    assert len(provider.calls) == 1
    context = str(provider.calls[0][0])
    assert "192.168" not in context
    assert "host-a" not in context
    assert str(seeded["host"].id) not in context
    assert ask(client, seeded, actor_headers, language="pt-BR").status_code == 200
    assert len(provider.calls) == 2
    assert len(administrative_session.exec(select(AIExplanationRecord)).all()) == 2
    assert len(administrative_session.exec(select(AIUsageRecord)).all()) == 2


def test_tenant_checked_before_cache(
    client, administrative_session, actor_headers, provider,
):
    seeded = seed_read_graph(administrative_session)
    assert ask(client, seeded, actor_headers).status_code == 200
    response = ask(
        client, seeded, actor_headers, org_id=seeded["other_org"].id,
    )
    assert response.status_code == 404
    assert len(provider.calls) == 1


@pytest.mark.parametrize("defect", ["count", "failure", "reference"])
def test_invalid_output_keeps_usage_without_cache(
    client, administrative_session, actor_headers, provider, defect,
):
    seeded = seed_read_graph(administrative_session)
    provider.defect = defect
    assert ask(client, seeded, actor_headers).status_code == 502
    assert administrative_session.exec(select(AIExplanationRecord)).all() == []
    assert len(administrative_session.exec(select(AIUsageRecord)).all()) == 1


def test_shared_daily_limit(client, administrative_session, actor_headers, provider):
    seeded = seed_read_graph(administrative_session)
    assert ask(client, seeded, actor_headers).status_code == 200
    assert ask(client, seeded, actor_headers, scope="host").status_code == 200
    response = client.post(
        "/api/v1/ai/chat",
        json={"scope": "scan", "context_id": str(seeded["scan"].scan_id),
              "question": "What should I fix?"},
        headers=seeded["headers"][str(seeded["org"].id)],
    )
    assert response.status_code == 429
    assert ask(client, seeded, actor_headers, language="ru").status_code == 429
    assert ask(client, seeded, actor_headers).status_code == 200


def test_host_cache_refreshes_for_new_scan(
    client, administrative_session, actor_headers, provider,
):
    seeded = seed_read_graph(administrative_session)
    assert ask(client, seeded, actor_headers, scope="host").status_code == 200
    scan = ScanRecord(
        scan_id=uuid4(), org_id=seeded["org"].id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24", scan_mode="quick", status="completed",
        metadata_json={},
    )
    administrative_session.add(scan)
    administrative_session.flush()
    administrative_session.add(ScanHostRecord(
        scan_id=scan.scan_id, host_id=seeded["host"].id, ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff", hostname="host-a", vendor="Acme",
    ))
    administrative_session.commit()
    response = ask(client, seeded, actor_headers, scope="host")
    assert response.status_code == 200, response.text
    assert len(provider.calls) == 2
    assert provider.calls[-1][0]["facts"]["vulnerability_count"] == 0
    row = administrative_session.exec(select(AIExplanationRecord)).one()
    assert row.scan_id == scan.scan_id


def test_explanation_scrubs_credentials_before_storage(
    client, administrative_session, actor_headers, provider, monkeypatch,
):
    seeded = seed_read_graph(administrative_session)
    original = provider.explain_context

    def with_secret(context, *, scope, language):
        result = original(context, scope=scope, language=language)
        result.in_short = "Never share password=private-value with others."
        return result

    monkeypatch.setattr(provider, "explain_context", with_secret)
    response = ask(client, seeded, actor_headers)
    assert response.status_code == 200
    assert "private-value" not in response.text
    row = administrative_session.exec(select(AIExplanationRecord)).one()
    assert "private-value" not in str(row.explanation_json)


@pytest.mark.parametrize("scope", ["scan", "host"])
def test_deleting_context_removes_its_explanation(
    client, administrative_session, actor_headers, provider, scope,
):
    seeded = seed_read_graph(administrative_session)
    headers = actor_headers(seeded["org"].id, "admin")
    assert ask(client, seeded, lambda *args: headers, scope=scope).status_code == 200
    resource = "scans" if scope == "scan" else "hosts"
    context_id = seeded["scan"].scan_id if scope == "scan" else seeded["host"].id
    response = client.delete(f"/api/v1/{resource}/{context_id}", headers=headers)
    assert response.status_code in (200, 204), response.text
    assert administrative_session.exec(select(AIExplanationRecord)).all() == []


@pytest.mark.parametrize('scope', ['scan', 'host'])
@pytest.mark.parametrize('language', ['en', 'pt-BR', 'ru'])
def test_saved_explanation_reopens_without_generation_even_when_ai_is_unavailable(
    client, administrative_session, actor_headers, provider, scope, language,
    monkeypatch,
):
    seeded = seed_read_graph(administrative_session)
    first = ask(client, seeded, actor_headers, scope=scope, language=language)
    assert first.status_code == 200, first.text
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={'ai_enabled': False}
    )
    monkeypatch.setattr('api.routers.ai.explanation_context', lambda *args: pytest.fail(
        'A saved explanation must not rebuild its model context'
    ))
    second = ask(client, seeded, actor_headers, scope=scope, language=language)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    assert len(provider.calls) == 1


@pytest.mark.parametrize('scope', ['scan', 'host'])
def test_concurrent_portuguese_requests_share_one_saved_explanation(
    client, administrative_session, actor_headers, provider, monkeypatch, scope,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from api.db.session import get_session
    from api.routers import ai
    from sqlmodel import Session

    seeded = seed_read_graph(administrative_session)
    headers = actor_headers(seeded['org'].id, 'viewer')
    context_id = seeded['scan'].scan_id if scope == 'scan' else seeded['host'].id
    entered, authorized, release = Event(), Event(), Event()
    resolve = ai._resolve_scan_id
    original = provider.explain_context
    resolutions = []

    def independent_session():
        with Session(administrative_session.get_bind()) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_session, independent_session)

    def resolved(*args):
        result = resolve(*args)
        resolutions.append(result)
        if len(resolutions) == 2:
            authorized.set()
        return result

    def explain(context, *, scope, language):
        entered.set()
        assert release.wait(5)
        return original(context, scope=scope, language=language)

    monkeypatch.setattr(ai, '_resolve_scan_id', resolved)
    monkeypatch.setattr(provider, 'explain_context', explain)

    def request():
        return client.post('/api/v1/ai/explain', json={
            'scope': scope, 'context_id': str(context_id), 'language': 'pt-BR',
        }, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request)
        assert entered.wait(5)
        second = pool.submit(request)
        try:
            assert authorized.wait(5)
        finally:
            release.set()
        first_result, second_result = first.result(), second.result()
    assert first_result.status_code == second_result.status_code == 200
    assert first_result.json() == second_result.json()
    assert len(provider.calls) == 1
