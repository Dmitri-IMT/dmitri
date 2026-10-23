from types import SimpleNamespace

from api.core.config import get_settings
from api.main import app
from api.models.identity import User
from api.models.persistence import AIChatMessageRecord, AIUsageRecord
from api.schemas.read import (
    FindingEvidenceConfidenceCounts,
    FindingEvidenceMethodCounts,
    FindingEvidenceSummary,
)
from api.services.ai.context import FindingChatContext, HostChatContext
from api.services.ai.openai_responses import (
    AIProviderError,
    ChatTextPart,
    ProviderChatAnswer,
)
from read_factories import seed_read_graph
from sqlmodel import select


def _answer(text: str) -> ProviderChatAnswer:
    return ProviderChatAnswer(
        parts=(ChatTextPart(text=text, citations=()),), sources=frozenset()
    )


class _FakeProvider:
    def answer_question(self, context, question, *, language="en"):
        assert question == "o que devo corrigir?"
        assert context.top_findings
        return _answer("Revise finding_1 primeiro.")


class _ScopedFakeProvider:
    def answer_question(self, context, question, *, language="en"):
        assert question == "explique este contexto"
        assert isinstance(context, FindingChatContext | HostChatContext)
        return _answer("Explicação fundamentada sobre finding_1.")


def _enable_ai(monkeypatch):
    settings_update = {
        "ai_enabled": True,
        "ai_api_key": "test-key",  # pragma: allowlist secret
    }
    settings = get_settings().model_copy(
        update=settings_update
    )
    app.dependency_overrides[get_settings] = lambda: settings


def test_ai_usage_is_scoped_and_exposes_only_metadata(
    client, administrative_session, actor_headers
):
    seeded = seed_read_graph(administrative_session)
    administrative_session.add_all(
        [
            AIUsageRecord(
                org_id=seeded["org"].id,
                scan_id=seeded["scan"].scan_id,
                operation="chat",
                provider="groq",
                model="test-model",
                status="success",
                input_tokens=12,
                output_tokens=7,
                total_tokens=19,
                latency_ms=23,
                http_status=200,
                request_id="req-test",
            ),
            AIUsageRecord(
                org_id=seeded["org"].id,
                operation="scan_analysis",
                provider="groq",
                model="test-model",
                status="error",
                error_code="provider_rate_limited",
                http_status=429,
            ),
        ]
    )
    administrative_session.commit()

    response = client.get(
        "/api/v1/ai/usage?limit=2",
        headers=actor_headers(seeded["org"].id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "requests": 2,
        "input_tokens": 12,
        "output_tokens": 7,
        "total_tokens": 19,
        "errors": 1,
    }
    assert len(body["data"]) == 2
    success = next(item for item in body["data"] if item["status"] == "success")
    assert success["request_id"] == "req-test"
    assert all("prompt" not in item for item in body["data"])


def test_context_chat_scan_returns_grounded_response_without_calling_the_provider(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    monkeypatch.setattr(
        "api.routers.ai.build_ai_provider", lambda settings: _FakeProvider()
    )
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "o que devo corrigir?",
                "scope": "scan",
                "context_id": str(seeded["scan"].scan_id),
            },
            headers=actor_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == "Revise Vulnerable service primeiro."
    assert len(response.json()["referenced_finding_ids"]) == 1


def test_context_chat_scan_maps_provider_rate_limit_to_api_error(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)

    class _RateLimitedProvider:
        def answer_question(self, context, question, *, language="en"):
            raise AIProviderError(
                "provider_rate_limited", retryable=True, retry_after_seconds=42
            )

    monkeypatch.setattr(
        "api.routers.ai.build_ai_provider",
        lambda settings: _RateLimitedProvider(),
    )
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "o que devo corrigir?",
                "scope": "scan",
                "context_id": str(seeded["scan"].scan_id),
                "language": "pt-BR",
            },
            headers=actor_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ai_rate_limited"
    assert "42 segundos" in response.json()["error"]["message"]


def test_context_chat_finding_returns_grounded_response(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    monkeypatch.setattr(
        "api.routers.ai.build_ai_provider",
        lambda settings: _ScopedFakeProvider(),
    )
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "explique este contexto",
                "scope": "finding",
                "context_id": str(seeded["finding"].finding_id),
            },
            headers=actor_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Explicação fundamentada sobre Vulnerable service."
    )


def test_context_chat_host_returns_grounded_response(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    monkeypatch.setattr(
        "api.routers.ai.build_ai_provider",
        lambda settings: _ScopedFakeProvider(),
    )
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "explique este contexto",
                "scope": "host",
                "context_id": str(seeded["host"].id),
            },
            headers=actor_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Explicação fundamentada sobre Vulnerable service."
    )


def test_host_chat_route_passes_full_filtered_summary_to_provider(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    summary = FindingEvidenceSummary(
        scope="filtered_findings",
        total_records=143,
        by_method=FindingEvidenceMethodCounts(
            version_correlation=40, configuration_observation=20,
            specific_check=30, textual_reference=3, unknown=50,
        ),
        by_confidence=FindingEvidenceConfidenceCounts(
            tentative=40, probable=25, confirmed=28, unknown=50,
        ),
        conflicting_records=7,
        demonstrated_records=12,
    )
    from api.services.read import list_findings

    page = list_findings(
        administrative_session, org_id=seeded["org"].id,
        host_id=seeded["host"].id, per_page=1,
    )
    assert len(page.data) == 1
    monkeypatch.setattr(
        "api.routers.ai.list_findings",
        lambda *args, **kwargs: SimpleNamespace(
            data=page.data, evidence_summary=summary
        ),
    )
    _enable_ai(monkeypatch)

    class _SummaryProvider:
        def answer_question(self, context, question, *, language="en"):
            assert isinstance(context, HostChatContext)
            assert len(context.findings) == 1
            assert context.evidence_summary == summary
            return _answer("Há registros para revisar em finding_1.")

    monkeypatch.setattr(
        "api.routers.ai.build_ai_provider", lambda settings: _SummaryProvider()
    )
    headers = actor_headers(seeded["org"].id, "viewer")
    user = administrative_session.exec(
        select(User).where(User.org_id == seeded["org"].id)
    ).one()
    historical = AIChatMessageRecord(
        scan_id=seeded["scan"].scan_id,
        user_id=user.id,
        scope_type="host",
        scope_id=seeded["host"].id,
        question="pergunta antiga",
        answer="resposta histórica intacta",
        uncertainties_json=["limite histórico"],
        referenced_finding_ids_json=[str(seeded["finding"].finding_id)],
    )
    administrative_session.add(historical)
    administrative_session.commit()
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "explique este contexto", "scope": "host",
                "context_id": str(seeded["host"].id),
            },
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Há registros para revisar em Vulnerable service."
    )

    history = client.get(
        "/api/v1/ai/chat/history",
        params={"scope": "host", "context_id": str(seeded["host"].id)},
        headers=headers,
    )
    assert history.status_code == 200
    old_message = next(
        item for item in history.json()["data"]
        if item["question"] == "pergunta antiga"
    )
    assert old_message["answer"] == "resposta histórica intacta"
    assert old_message["uncertainties"] == ["limite histórico"]


def test_context_chat_finding_unknown_finding_returns_404(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "explique este contexto",
                "scope": "finding",
                "context_id": "00000000-0000-4000-8000-000000000000",
            },
            headers=actor_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 404


def test_context_chat_stops_at_the_daily_question_limit(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    headers = actor_headers(seeded["org"].id, "viewer")
    user = administrative_session.exec(
        select(User).where(User.org_id == seeded["org"].id)
    ).one()
    administrative_session.add_all(
        AIUsageRecord(
            org_id=seeded["org"].id,
            user_id=user.id,
            operation="chat",
            provider="openai",
            model="gpt-6-luna",
            status="success",
        )
        for _ in range(3)
    )
    administrative_session.commit()
    settings = get_settings().model_copy(
        update={
            "ai_enabled": True,
            "ai_api_key": "test-key",  # pragma: allowlist secret
            "ai_chat_daily_limit": 3,
        }
    )
    app.dependency_overrides[get_settings] = lambda: settings

    def _no_provider(settings):
        raise AssertionError("the provider must not be called over the limit")

    monkeypatch.setattr("api.routers.ai.build_ai_provider", _no_provider)
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "o que devo corrigir?",
                "scope": "scan",
                "context_id": str(seeded["scan"].scan_id),
                "language": "pt-BR",
            },
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ai_daily_limit"
    assert "3" in response.json()["error"]["message"]


def test_context_chat_removes_secrets_before_the_provider_and_history(
    client, administrative_session, actor_headers, monkeypatch
):
    seeded = seed_read_graph(administrative_session)
    _enable_ai(monkeypatch)
    received = []

    class _RecordingProvider:
        def answer_question(self, context, question, *, language="en"):
            received.append(question)
            return _answer("Troque a senha de finding_1.")

    monkeypatch.setattr(
        "api.routers.ai.build_ai_provider", lambda settings: _RecordingProvider()
    )
    try:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "question": "my password: hunter2 on 192.168.1.10",
                "scope": "scan",
                "context_id": str(seeded["scan"].scan_id),
            },
            headers=actor_headers(seeded["org"].id, "viewer"),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert received == ["my password: [removed] on [removed]"]
    saved = administrative_session.exec(select(AIChatMessageRecord)).one()
    assert saved.question == "my password: [removed] on [removed]"
