from __future__ import annotations

import json

import httpx
import pytest
from api.schemas.ai import ProviderAIChatResponse, ProviderScanAIAnalysis
from api.schemas.read import SeverityBreakdown
from api.services.ai.context import ScanAIContext
from api.services.ai.groq import SYSTEM_PROMPT, AIProviderError, GroqProvider

TEST_TOKEN = "test-token"


def _context() -> ScanAIContext:
    return ScanAIContext(
        scan_mode="quick",
        duration_seconds=10,
        host_count=1,
        total_findings=0,
        scored_findings=0,
        confirmed_findings=0,
        kev_findings=0,
        average_risk_score=None,
        max_risk_score=None,
        severity=SeverityBreakdown(),
        top_findings=[],
    )


def _analysis() -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        executive_summary="Nenhum risco prioritário foi identificado.",
        overall_assessment="O scan não apresentou findings para priorização.",
        plain_language_summary="Nada urgente apareceu neste resultado.",
        priority_actions=[],
        important_findings=[],
        uncertainties=["A ausência de findings não comprova ausência de risco."],
    )


def _provider(handler) -> GroqProvider:
    return GroqProvider(
        api_key=TEST_TOKEN,
        model="openai/gpt-oss-120b",
        base_url="https://api.groq.test/openai/v1/",
        timeout_seconds=3,
        max_output_tokens=1024,
        reasoning_effort="low",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_groq_provider_requests_strict_structured_output():
    captured = {}
    context = _context()

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": _analysis().model_dump_json(),
                        }
                    }
                ]
            },
        )

    result = _provider(handler).analyze_scan(context)

    assert result == _analysis()
    assert captured["authorization"] == f"Bearer {TEST_TOKEN}"
    payload = captured["payload"]
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["max_completion_tokens"] == 1024
    assert payload["reasoning_effort"] == "low"
    assert payload["include_reasoning"] is False
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert "Never claim a network" in payload["messages"][0]["content"]
    assert TEST_TOKEN not in json.dumps(payload)
    assert '"context_version":"2"' in payload["messages"][1]["content"]
    assert "scan_id" not in payload["messages"][1]["content"]


def test_system_prompt_requests_english_prose():
    assert "English" in SYSTEM_PROMPT
    assert "Portuguese" not in SYSTEM_PROMPT


def test_groq_provider_repair_sends_codes_not_rejected_prose():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": _analysis().model_dump_json(),
                        }
                    }
                ]
            },
        )

    _provider(handler).repair_analysis(
        _context(),
        ("executive_summary:safety_certification",),
    )

    repair_prompt = captured["payload"]["messages"][1]["content"]
    assert "executive_summary:safety_certification" in repair_prompt
    assert "Your network is safe." not in repair_prompt


def test_groq_provider_maps_timeout_without_leaking_details():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive upstream detail", request=request)

    with pytest.raises(AIProviderError) as captured:
        _provider(handler).analyze_scan(_context())

    assert captured.value.code == "provider_timeout"
    assert captured.value.retryable is True
    assert str(captured.value) == "provider_timeout"


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "provider_authentication_failed", False),
        (422, "invalid_provider_response", True),
        (429, "provider_rate_limited", True),
        (500, "provider_unavailable", True),
    ],
)
def test_groq_provider_maps_http_errors(status, code, retryable):
    provider = _provider(lambda request: httpx.Response(status, json={"secret": "x"}))

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == code
    assert captured.value.retryable is retryable
    assert "secret" not in str(captured.value)


def test_groq_provider_classifies_oversized_context_without_retry_wait():
    provider = _provider(
        lambda request: httpx.Response(
            413,
            headers={"x-ratelimit-reset-tokens": "7.66s"},
            json={"error": {"message": "request too large"}},
        )
    )

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == "provider_context_too_large"
    assert captured.value.retryable is False


def test_groq_provider_exposes_rate_limit_wait_time():
    provider = _provider(
        lambda request: httpx.Response(
            429,
            headers={"x-ratelimit-reset-tokens": "7.66s"},
            json={"error": {"message": "rate limited"}},
        )
    )

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == "provider_rate_limited"
    assert captured.value.retry_after_seconds == 8


def test_groq_provider_rejects_invalid_payload():
    provider = _provider(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )
    )

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == "invalid_provider_response"
    assert captured.value.retryable is True


def test_groq_provider_answers_chat_with_bounded_structured_schema():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": ProviderAIChatResponse(
                                answer="Priorize a atualização do serviço exposto.",
                                uncertainties=[
                                    "O scan não confirma exploração ativa."
                                ],
                                referenced_finding_refs=["finding_1"],
                            ).model_dump_json(),
                        }
                    }
                ]
            },
        )

    result = _provider(handler).answer_question(
        {"top_findings": [{"finding_ref": "finding_1"}]},
        "O que devo corrigir primeiro?",
    )

    assert result.answer.startswith("Priorize")
    payload = captured["payload"]
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["max_completion_tokens"] == 1024
    assert "O que devo corrigir primeiro?" in payload["messages"][1]["content"]
