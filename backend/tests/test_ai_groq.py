from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from api.schemas.ai import ScanAIAnalysis
from api.schemas.read import SeverityBreakdown
from api.services.ai.context import ScanAIContext
from api.services.ai.groq import SYSTEM_PROMPT, AIProviderError, GroqProvider

TEST_TOKEN = "test-token"


def _context() -> ScanAIContext:
    return ScanAIContext(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
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


def _analysis() -> ScanAIAnalysis:
    return ScanAIAnalysis(
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
                            "content": json.dumps(
                                _analysis().model_dump(mode="json")
                            )
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
    assert TEST_TOKEN not in json.dumps(payload)
    assert str(context.scan_id) in payload["messages"][1]["content"]


def test_system_prompt_requests_english_prose():
    assert "English" in SYSTEM_PROMPT
    assert "Portuguese" not in SYSTEM_PROMPT
    assert "Brazilian Portuguese" not in SYSTEM_PROMPT


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
