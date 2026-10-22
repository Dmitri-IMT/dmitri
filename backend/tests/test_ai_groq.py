from __future__ import annotations

import json

import httpx
import pytest
from api.schemas.ai import (
    ProviderAIChatResponse,
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
)
from api.schemas.read import (
    FindingEvidenceConfidenceCounts,
    FindingEvidenceMethodCounts,
    FindingEvidenceSummary,
    SeverityBreakdown,
)
from api.services.ai.context import (
    AI_CONTEXT_VERSION,
    AIFindingContext,
    FindingChatContext,
    ScanAIContext,
)
from api.services.ai.groq import (
    AI_PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_CHAT_PROMPT,
    AIProviderError,
    GroqProvider,
)

TEST_TOKEN = "test-token"


def _context(
    *, completeness: str = "complete", stopped_by: str | None = None
) -> ScanAIContext:
    return ScanAIContext(
        scan_mode="quick",
        evidence_completeness=completeness,
        duration_seconds=10,
        stopped_by=stopped_by,
        host_count=1,
        total_findings=0,
        scored_findings=0,
        confirmed_findings=0,
        kev_findings=0,
        average_risk_score=None,
        max_risk_score=None,
        severity=SeverityBreakdown(),
        top_findings=[],
        evidence_summary=FindingEvidenceSummary(
            scope="scan",
            total_records=0,
            by_method=FindingEvidenceMethodCounts(
                version_correlation=0, configuration_observation=0,
                specific_check=0, textual_reference=0, unknown=0,
            ),
            by_confidence=FindingEvidenceConfidenceCounts(
                tentative=0, probable=0, confirmed=0, unknown=0,
            ),
            conflicting_records=0,
            demonstrated_records=0,
        ),
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

    provider = _provider(handler)
    result = provider.analyze_scan(context)

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
    assert (
        f'"context_version":"{AI_CONTEXT_VERSION}"'
        in payload["messages"][1]["content"]
    )
    assert not payload["messages"][1]["content"].startswith("Coverage limit:")
    assert "scan_id" not in payload["messages"][1]["content"]
    usage = provider.drain_usage_events()
    assert usage[0].operation == "scan_analysis"
    assert usage[0].input_tokens is None


@pytest.mark.parametrize(
    ("stopped_by", "reason"),
    [
        ("operator", "An operator stopped the scan early."),
        ("timeout", "A time limit stopped the scan."),
        ("error", "An error stopped the scan early."),
    ],
)
def test_partial_scan_prompt_opens_with_coverage_limit(stopped_by, reason):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _analysis().model_dump_json()}}]},
        )

    _provider(handler).analyze_scan(
        _context(completeness="partial", stopped_by=stopped_by)
    )

    payload = captured["payload"]
    user_prompt = payload["messages"][1]["content"]
    assert user_prompt.startswith(
        f"Coverage limit: this scan is partial. {reason} A missing finding is not "
        "evidence that a vulnerability is absent."
    )
    assert "Never infer that the scan is clean" in payload["messages"][0]["content"]


def test_groq_provider_warns_when_completeness_is_unknown():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _analysis().model_dump_json()}}]},
        )

    _provider(handler).analyze_scan(_context(completeness="unknown"))

    assert captured["payload"]["messages"][1]["content"].startswith(
        "Coverage limit: this scan does not report whether every check finished. "
        "A missing finding is not evidence that a vulnerability is absent."
    )


def test_groq_provider_keeps_coverage_notice_on_chunk_and_repair():
    prompts = []

    def handler(request: httpx.Request) -> httpx.Response:
        prompts.append(json.loads(request.content)["messages"][1]["content"])
        child = ProviderScanAIChildAnalysis(
            priority_actions=[],
            important_findings=[],
            uncertainties=[],
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": child.model_dump_json()}}]},
        )

    provider = _provider(handler)
    context = _context(completeness="partial", stopped_by="timeout")
    provider.analyze_chunk(context)
    provider.repair_chunk(context, ("important_findings:style",))

    assert len(prompts) == 2
    for prompt in prompts:
        assert prompt.startswith(
            "Coverage limit: this scan is partial. A time limit stopped the scan. "
            "A missing finding is not evidence that a vulnerability is absent."
        )

def test_scan_analysis_operations_use_small_completion_budgets():
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(payload["max_completion_tokens"])
        user_prompt = payload["messages"][1]["content"]
        content = (
            json.dumps(
                {
                    "priority_actions": [],
                    "important_findings": [],
                    "uncertainties": [],
                }
            )
            if "CHUNK_CONTEXT_JSON:" in user_prompt
            else _analysis().model_dump_json()
        )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    provider = _provider(handler)
    context = _context()
    child = provider.analyze_chunk(context)
    provider.repair_chunk(context, ("style",))
    provider.synthesize_scan(context, [child.model_dump(mode="json")], ())

    assert captured == [1_536, 1_536, 1_200]


def test_groq_provider_records_usage_without_prompt_content():
    provider = _provider(
        lambda request: httpx.Response(
            200,
            headers={"x-request-id": "req-test"},
            json={
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 7,
                    "total_tokens": 19,
                },
                "choices": [
                    {"message": {"content": _analysis().model_dump_json()}}
                ],
            },
        )
    )

    provider.analyze_scan(_context())
    event = provider.drain_usage_events()[0]
    assert event.input_tokens == 12
    assert event.output_tokens == 7
    assert event.total_tokens == 19
    assert event.request_id == "req-test"
    assert event.latency_ms is not None


def test_system_prompt_uses_a_language_placeholder():
    assert "{language_name}" in SYSTEM_PROMPT


def test_system_prompt_preserves_evidence_uncertainty_and_sample_limits():
    assert AI_PROMPT_VERSION == "8"
    prompts = " ".join(f"{SYSTEM_PROMPT} {USER_CHAT_PROMPT}".split())
    for rule in (
        "inconclusive evidence",
        "conflicting evidence",
        "truncated evidence",
        "Negative observations apply",
        "never prove that a target is safe",
        "evidence_summary describes the full scope",
        "Do not treat a sample as a full list",
    ):
        assert rule in prompts


@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "English"), ("pt-BR", "Brazilian Portuguese"), ("ru", "Russian")],
)
def test_groq_provider_sends_requested_analysis_language(language, expected):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _analysis().model_dump_json()}}]},
        )

    _provider(handler).analyze_scan(_context(), language=language)

    assert f"Write all explanatory prose in {expected}." in captured["payload"][
        "messages"
    ][0]["content"]
    system_prompt = captured["payload"]["messages"][0]["content"]
    assert "Write calmly in the requested language" in system_prompt
    assert "Write calm, plain English" not in system_prompt


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
        (
            "executive_summary:safety_certification",
            "analysis contains an unknown reference",
            "analysis contains duplicate finding references",
        ),
    )

    repair_prompt = captured["payload"]["messages"][1]["content"]
    assert "executive_summary:safety_certification" in repair_prompt
    assert "do not describe a network, machine, or service as safe" in repair_prompt
    assert "use only finding_N and machine_N references" in repair_prompt
    assert "one important finding explanation per finding_ref" in repair_prompt
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
        FindingChatContext(
            finding=AIFindingContext(
                finding_ref="finding_1",
                machine_ref=None,
                cve_id=None,
                cvss_score=None,
                severity="high",
                confidence=None,
                evidence_basis="unknown",
                detection_method="specific_check",
                evidence_status="inconclusive",
                evidence_truncated=True,
                risk_score=None,
                exploitability=None,
                epss_score=None,
                epss_percentile=None,
                is_kev=False,
                known_ransomware=False,
            ),
            evidence_summary=FindingEvidenceSummary(
                scope="filtered_findings", total_records=1,
                by_method=FindingEvidenceMethodCounts(
                    version_correlation=0, configuration_observation=0,
                    specific_check=0, textual_reference=0, unknown=1,
                ),
                by_confidence=FindingEvidenceConfidenceCounts(
                    tentative=0, probable=0, confirmed=0, unknown=1,
                ),
                conflicting_records=0, demonstrated_records=0,
            ),
        ),
        "O que devo corrigir primeiro?",
    )

    assert result.answer.startswith("Priorize")
    payload = captured["payload"]
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["max_completion_tokens"] == 1024
    assert "O que devo corrigir primeiro?" in payload["messages"][1]["content"]
    submitted_context = payload["messages"][1]["content"]
    assert '"evidence_status":"inconclusive"' in submitted_context
    assert '"evidence_truncated":true' in submitted_context
    assert '"scope":"filtered_findings"' in submitted_context
    system_prompt = payload["messages"][0]["content"]
    assert "never prove that a target is safe" in system_prompt
    assert "Never elevate" in submitted_context
