from __future__ import annotations

import json

import httpx
import pytest
from api.core.config import Settings
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
    AIFindingContext,
    FindingChatContext,
    ScanAIContext,
)
from api.services.ai.openai_responses import (
    AI_PROMPT_VERSION,
    OPENAI_RESPONSES_URL,
    SYSTEM_PROMPT,
    USER_CHAT_PROMPT,
    AIProviderError,
    OpenAIResponsesProvider,
    build_ai_provider,
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


def _completed(text: str, **extra: object) -> dict[str, object]:
    return {
        "id": "resp_test",
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            },
        ],
        **extra,
    }


def _provider(handler) -> OpenAIResponsesProvider:
    return OpenAIResponsesProvider(
        api_key=TEST_TOKEN,
        model="gpt-6-luna",
        timeout_seconds=3,
        max_output_tokens=1024,
        reasoning_effort="high",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _capture(captured: dict[str, object], text: str):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_completed(text))

    return handler


def test_provider_requests_responses_api_with_strict_output_and_no_storage():
    captured: dict[str, object] = {}
    provider = _provider(_capture(captured, _analysis().model_dump_json()))

    result = provider.analyze_scan(_context())

    assert result == _analysis()
    assert captured["url"] == OPENAI_RESPONSES_URL
    assert captured["authorization"] == f"Bearer {TEST_TOKEN}"
    payload = captured["payload"]
    assert payload["model"] == "gpt-6-luna"
    assert payload["store"] is False
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["max_output_tokens"] == 1024
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert set(payload) == {
        "model",
        "instructions",
        "input",
        "store",
        "reasoning",
        "max_output_tokens",
        "text",
    }
    assert "Never claim a network" in payload["instructions"]
    assert TEST_TOKEN not in json.dumps(payload)
    assert '"context_version":"5"' in payload["input"]
    assert not payload["input"].startswith("Coverage limit:")
    assert "scan_id" not in payload["input"]


def test_every_operation_uses_the_configured_output_budget():
    budgets = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        budgets.append(payload["max_output_tokens"])
        child = ProviderScanAIChildAnalysis(
            priority_actions=[], important_findings=[], uncertainties=[]
        )
        text = (
            child.model_dump_json()
            if "CHUNK_CONTEXT_JSON:" in payload["input"]
            else _analysis().model_dump_json()
        )
        return httpx.Response(200, json=_completed(text))

    provider = _provider(handler)
    context = _context()
    child = provider.analyze_chunk(context)
    provider.repair_chunk(context, ("style",))
    provider.synthesize_scan(context, [child.model_dump(mode="json")], ())
    provider.repair_analysis(context, ("style",))

    assert budgets == [1024, 1024, 1024, 1024]


@pytest.mark.parametrize(
    ("stopped_by", "reason"),
    [
        ("operator", "An operator stopped the scan early."),
        ("timeout", "A time limit stopped the scan."),
        ("error", "An error stopped the scan early."),
    ],
)
def test_partial_scan_prompt_opens_with_coverage_limit(stopped_by, reason):
    captured: dict[str, object] = {}

    _provider(_capture(captured, _analysis().model_dump_json())).analyze_scan(
        _context(completeness="partial", stopped_by=stopped_by)
    )

    payload = captured["payload"]
    assert payload["input"].startswith(
        f"Coverage limit: this scan is partial. {reason} A missing finding is not "
        "evidence that a vulnerability is absent."
    )
    assert "Never infer that the scan is clean" in payload["instructions"]


def test_provider_warns_when_completeness_is_unknown():
    captured: dict[str, object] = {}

    _provider(_capture(captured, _analysis().model_dump_json())).analyze_scan(
        _context(completeness="unknown")
    )

    assert captured["payload"]["input"].startswith(
        "Coverage limit: this scan does not report whether every check finished. "
        "A missing finding is not evidence that a vulnerability is absent."
    )


def test_provider_keeps_coverage_notice_on_chunk_and_repair():
    prompts = []

    def handler(request: httpx.Request) -> httpx.Response:
        prompts.append(json.loads(request.content)["input"])
        child = ProviderScanAIChildAnalysis(
            priority_actions=[],
            important_findings=[],
            uncertainties=[],
        )
        return httpx.Response(200, json=_completed(child.model_dump_json()))

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


def test_provider_records_usage_with_cached_and_reasoning_tokens():
    provider = _provider(
        lambda request: httpx.Response(
            200,
            headers={"x-request-id": "req-test"},
            json=_completed(
                _analysis().model_dump_json(),
                usage={
                    "input_tokens": 12,
                    "input_tokens_details": {"cached_tokens": 4},
                    "output_tokens": 7,
                    "output_tokens_details": {"reasoning_tokens": 5},
                    "total_tokens": 19,
                },
            ),
        )
    )

    provider.analyze_scan(_context())
    event = provider.drain_usage_events()[0]
    assert event.operation == "scan_analysis"
    assert event.status == "success"
    assert event.input_tokens == 12
    assert event.cached_input_tokens == 4
    assert event.output_tokens == 7
    assert event.reasoning_tokens == 5
    assert event.total_tokens == 19
    assert event.request_id == "req-test"
    assert event.latency_ms is not None


def test_system_prompt_uses_a_language_placeholder():
    assert "{language_name}" in SYSTEM_PROMPT


def test_system_prompt_preserves_evidence_uncertainty_and_sample_limits():
    assert AI_PROMPT_VERSION == "7"
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
def test_provider_sends_requested_analysis_language(language, expected):
    captured: dict[str, object] = {}

    _provider(_capture(captured, _analysis().model_dump_json())).analyze_scan(
        _context(), language=language
    )

    instructions = captured["payload"]["instructions"]
    assert f"Write all explanatory prose in {expected}." in instructions
    assert "Write calmly in the requested language" in instructions
    assert "Write calm, plain English" not in instructions


def test_provider_repair_sends_codes_not_rejected_prose():
    captured: dict[str, object] = {}

    _provider(_capture(captured, _analysis().model_dump_json())).repair_analysis(
        _context(),
        (
            "executive_summary:safety_certification",
            "analysis contains an unknown reference",
            "analysis contains duplicate finding references",
        ),
    )

    repair_prompt = captured["payload"]["input"]
    assert "executive_summary:safety_certification" in repair_prompt
    assert "do not describe a network, machine, or service as safe" in repair_prompt
    assert "use only finding_N and machine_N references" in repair_prompt
    assert "one important finding explanation per finding_ref" in repair_prompt
    assert "Your network is safe." not in repair_prompt


def test_provider_maps_timeout_without_leaking_details():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive upstream detail", request=request)

    provider = _provider(handler)
    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == "provider_timeout"
    assert captured.value.retryable is True
    assert str(captured.value) == "provider_timeout"
    assert provider.drain_usage_events()[0].error_code == "provider_timeout"


@pytest.mark.parametrize(
    ("status", "error_code", "code", "retryable"),
    [
        (400, "invalid_request_error", "provider_request_rejected", False),
        (400, "context_length_exceeded", "provider_context_too_large", False),
        (401, None, "provider_authentication_failed", False),
        (403, None, "provider_authentication_failed", False),
        (404, "model_not_found", "provider_request_rejected", False),
        (408, None, "provider_timeout", True),
        (413, None, "provider_context_too_large", False),
        (422, None, "provider_request_rejected", False),
        (429, "rate_limit_exceeded", "provider_rate_limited", True),
        (429, "insufficient_quota", "provider_quota_exceeded", False),
        (500, None, "provider_unavailable", True),
        (503, None, "provider_unavailable", True),
    ],
)
def test_provider_maps_http_errors(status, error_code, code, retryable):
    body = {"error": {"code": error_code, "message": "secret upstream text"}}
    provider = _provider(lambda request: httpx.Response(status, json=body))

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == code
    assert captured.value.retryable is retryable
    assert "secret" not in str(captured.value)
    assert provider.drain_usage_events()[0].http_status == status


@pytest.mark.parametrize(
    ("headers", "seconds"),
    [
        ({"retry-after": "8"}, 8),
        ({"x-ratelimit-reset-requests": "1.5s"}, 2),
        ({"x-ratelimit-reset-tokens": "6m0s"}, 360),
        ({"x-ratelimit-reset-tokens": "250ms"}, 1),
        ({}, 60),
    ],
)
def test_provider_exposes_rate_limit_wait_time(headers, seconds):
    provider = _provider(
        lambda request: httpx.Response(
            429,
            headers=headers,
            json={"error": {"code": "rate_limit_exceeded"}},
        )
    )

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == "provider_rate_limited"
    assert captured.value.retry_after_seconds == seconds


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            {
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
            },
            "provider_output_truncated",
        ),
        (
            {
                "status": "incomplete",
                "incomplete_details": {"reason": "content_filter"},
            },
            "provider_refused",
        ),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "refusal", "refusal": "No."}],
                    }
                ],
            },
            "provider_refused",
        ),
        ({"status": "completed", "output": []}, "invalid_provider_response"),
        ({"status": "failed", "output": []}, "invalid_provider_response"),
        (_completed("not-json"), "invalid_provider_response"),
        (_completed('{"executive_summary": 1}'), "invalid_provider_response"),
    ],
)
def test_provider_fails_terminally_on_unusable_responses(body, code):
    provider = _provider(lambda request: httpx.Response(200, json=body))

    with pytest.raises(AIProviderError) as captured:
        provider.analyze_scan(_context())

    assert captured.value.code == code
    assert captured.value.retryable is False


def test_provider_answers_chat_with_bounded_structured_schema():
    captured: dict[str, object] = {}
    answer = ProviderAIChatResponse(
        answer="Priorize a atualização do serviço exposto.",
        uncertainties=["O scan não confirma exploração ativa."],
        referenced_finding_refs=["finding_1"],
    )

    result = _provider(_capture(captured, answer.model_dump_json())).answer_question(
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
    assert payload["text"]["format"]["name"] == "scan_ai_chat"
    assert payload["text"]["format"]["strict"] is True
    assert payload["max_output_tokens"] == 1024
    assert payload["store"] is False
    assert "tools" not in payload
    submitted = payload["input"]
    assert "O que devo corrigir primeiro?" in submitted
    assert '"evidence_status":"inconclusive"' in submitted
    assert '"evidence_truncated":true' in submitted
    assert '"scope":"filtered_findings"' in submitted
    assert "Never elevate" in submitted
    assert "never prove that a target is safe" in payload["instructions"]


def test_build_ai_provider_uses_settings_and_requires_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("AI_MODEL", "AI_REASONING_EFFORT", "AI_MAX_OUTPUT_TOKENS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_API_KEY", "")
    assert build_ai_provider(Settings(_env_file=None)) is None

    monkeypatch.setenv("AI_API_KEY", "sk-test")
    provider = build_ai_provider(Settings(_env_file=None))
    assert isinstance(provider, OpenAIResponsesProvider)
    assert provider.model == "gpt-6-luna"
    assert provider.reasoning_effort == "high"
    assert provider.max_output_tokens == 25_000
