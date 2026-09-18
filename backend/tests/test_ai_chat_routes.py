from api.core.config import get_settings
from api.main import app
from api.schemas.ai import ProviderAIChatResponse
from api.services.ai.groq import AIProviderError
from read_factories import seed_read_graph


class _FakeProvider:
    def answer_question(self, context, question):
        assert question == "o que devo corrigir?"
        assert context["top_findings"]
        return ProviderAIChatResponse(
            answer="Revise o achado prioritário.",
            uncertainties=[],
            referenced_finding_refs=["finding_1"],
        )


class _ScopedFakeProvider:
    def answer_question(self, context, question):
        assert question == "explique este contexto"
        assert "finding" in context or "host" in context
        return ProviderAIChatResponse(
            answer="Explicação fundamentada.",
            uncertainties=[],
            referenced_finding_refs=["finding_1"],
        )


def _enable_ai(monkeypatch):
    settings = get_settings().model_copy(
        update={"ai_enabled": True, "ai_api_key": "test-key"}
    )
    app.dependency_overrides[get_settings] = lambda: settings


def test_scan_chat_returns_grounded_response_without_calling_groq(
    client, administrative_session, bearer_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    monkeypatch.setattr(
        "api.routers.scans.build_ai_provider", lambda settings: _FakeProvider()
    )
    try:
        response = client.post(
            f"/api/v1/scans/{seeded['scan'].scan_id}/chat",
            json={"question": "o que devo corrigir?"},
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == "Revise o achado prioritário."
    assert len(response.json()["referenced_finding_ids"]) == 1


def test_scan_chat_maps_provider_rate_limit_to_api_error(
    client, administrative_session, bearer_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)

    class _RateLimitedProvider:
        def answer_question(self, context, question):
            raise AIProviderError(
                "provider_rate_limited", retryable=True, retry_after_seconds=42
            )

    monkeypatch.setattr(
        "api.routers.scans.build_ai_provider",
        lambda settings: _RateLimitedProvider(),
    )
    try:
        response = client.post(
            f"/api/v1/scans/{seeded['scan'].scan_id}/chat",
            json={"question": "o que devo corrigir?"},
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ai_rate_limited"
    assert "42 segundos" in response.json()["error"]["message"]


def test_finding_explain_returns_grounded_response(
    client, administrative_session, bearer_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    monkeypatch.setattr(
        "api.routers.findings.build_ai_provider",
        lambda settings: _ScopedFakeProvider(),
    )
    try:
        response = client.post(
            f"/api/v1/findings/{seeded['finding'].finding_id}/explain",
            json={"question": "explique este contexto"},
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == "Explicação fundamentada."


def test_host_explain_returns_grounded_response(
    client, administrative_session, bearer_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    monkeypatch.setattr(
        "api.routers.hosts.build_ai_provider",
        lambda settings: _ScopedFakeProvider(),
    )
    try:
        response = client.post(
            f"/api/v1/hosts/{seeded['host'].id}/explain",
            json={"question": "explique este contexto"},
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == "Explicação fundamentada."


def test_finding_explain_unknown_finding_returns_404(
    client, administrative_session, bearer_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    try:
        response = client.post(
            "/api/v1/findings/00000000-0000-4000-8000-000000000000/explain",
            json={"question": "explique este contexto"},
            headers=bearer_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 404
