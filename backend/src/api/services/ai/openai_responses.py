from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from api.core.config import Settings
from api.schemas.ai import (
    ProviderCVEFixResearch,
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
)
from api.services.ai.context import AIChatContext, FixResearchTarget, ScanAIContext

_ProviderResponseT = TypeVar("_ProviderResponseT", bound=BaseModel)
logger = logging.getLogger(__name__)

OPENAI_PROVIDER_ID = "openai"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
AI_PROMPT_VERSION = "10"

_INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"

USER_SCAN_PROMPT = """{coverage_notice}SCAN_CONTEXT_JSON:
{context_json}
"""

USER_CHUNK_PROMPT = """{coverage_notice}CHUNK_CONTEXT_JSON:
{context_json}
"""

USER_REPAIR_SCAN_PROMPT = """{coverage_notice}FAILED_CHECKS: {violation_codes}
CORRECTIONS: {violation_instructions}

SCAN_CONTEXT_JSON:
{context_json}
"""

USER_REPAIR_CHUNK_PROMPT = """{coverage_notice}FAILED_CHECKS: {violation_codes}
CORRECTIONS: {violation_instructions}

CHUNK_CONTEXT_JSON:
{context_json}
"""

USER_SYNTHESIS_PROMPT = """{coverage_notice}SYNTHESIS_CONTEXT_JSON:
{context_json}
"""

USER_RESEARCH_PROMPT = """RESEARCH_TARGET_JSON:
{context_json}
"""

USER_CHAT_PROMPT = """USER_QUESTION:
{question}

CONTEXT_JSON:
{context_json}
"""


class AIProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class ProviderUsageEvent:
    operation: str
    model: str
    status: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    http_status: int | None = None
    request_id: str | None = None
    error_code: str | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class UrlCitation:
    start: int
    end: int
    url: str


@dataclass(frozen=True, slots=True)
class ChatTextPart:
    text: str
    citations: tuple[UrlCitation, ...]


@dataclass(frozen=True, slots=True)
class ProviderChatAnswer:
    parts: tuple[ChatTextPart, ...]
    sources: frozenset[str]


class OpenAIResponsesProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        reasoning_effort: str,
        research_max_tool_calls: int = 10,
        chat_max_tool_calls: int = 10,
        search_location: dict[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.reasoning_effort = reasoning_effort
        self.research_max_tool_calls = research_max_tool_calls
        self.chat_max_tool_calls = chat_max_tool_calls
        self.search_location = search_location or {"type": "approximate"}
        self.client = client
        self._usage_events: list[ProviderUsageEvent] = []

    def drain_usage_events(self) -> list[ProviderUsageEvent]:
        events, self._usage_events = self._usage_events, []
        return events

    def analyze_scan(
        self, context: ScanAIContext, *, language: str = "en"
    ) -> ProviderScanAIAnalysis:
        return self._complete(
            USER_SCAN_PROMPT.format(
                coverage_notice=_coverage_notice(context),
                context_json=context.model_dump_json(),
            ),
            ProviderScanAIAnalysis,
            operation="scan_analysis",
            task="scan",
            language=language,
        )

    def analyze_chunk(
        self, context: ScanAIContext, *, language: str = "en"
    ) -> ProviderScanAIChildAnalysis:
        return self._complete(
            USER_CHUNK_PROMPT.format(
                coverage_notice=_coverage_notice(context),
                context_json=context.model_dump_json(),
            ),
            ProviderScanAIChildAnalysis,
            operation="finding_chunk",
            task="chunk",
            language=language,
        )

    def repair_analysis(
        self,
        context: ScanAIContext,
        violation_codes: tuple[str, ...],
        *,
        language: str = "en",
    ) -> ProviderScanAIAnalysis:
        return self._complete(
            USER_REPAIR_SCAN_PROMPT.format(
                coverage_notice=_coverage_notice(context),
                violation_codes=", ".join(violation_codes),
                violation_instructions=_writing_guidance(violation_codes),
                context_json=context.model_dump_json(),
            ),
            ProviderScanAIAnalysis,
            operation="analysis_repair",
            task="scan",
            repair=True,
            language=language,
        )

    def repair_chunk(
        self,
        context: ScanAIContext,
        violation_codes: tuple[str, ...],
        *,
        language: str = "en",
    ) -> ProviderScanAIChildAnalysis:
        return self._complete(
            USER_REPAIR_CHUNK_PROMPT.format(
                coverage_notice=_coverage_notice(context),
                violation_codes=", ".join(violation_codes),
                violation_instructions=_writing_guidance(violation_codes),
                context_json=context.model_dump_json(),
            ),
            ProviderScanAIChildAnalysis,
            operation="chunk_repair",
            task="chunk",
            repair=True,
            language=language,
        )

    def synthesize_scan(
        self,
        context: ScanAIContext,
        child_results: list[dict[str, object]],
        failed_refs: tuple[str, ...],
        *,
        language: str = "en",
    ) -> ProviderScanAIAnalysis:
        synthesis_context = {
            "aggregate": {
                "host_count": context.host_count,
                "stopped_by": context.stopped_by,
                "total_findings": context.total_findings,
                "scored_findings": context.scored_findings,
                "confirmed_findings": context.confirmed_findings,
                "evidence_completeness": context.evidence_completeness,
                "incomplete_check_count": context.incomplete_check_count,
                "evidence_summary": context.evidence_summary.model_dump(
                    mode="json"
                ),
                "kev_findings": context.kev_findings,
                "severity": context.severity.model_dump(mode="json"),
            },
            "validated_child_results": child_results,
            "failed_finding_refs": list(failed_refs),
            "kev_finding_refs": [
                finding.finding_ref
                for finding in context.top_findings
                if finding.is_kev
            ],
        }
        return self._complete(
            USER_SYNTHESIS_PROMPT.format(
                coverage_notice=_coverage_notice(context),
                context_json=json.dumps(synthesis_context, separators=(",", ":"))
            ),
            ProviderScanAIAnalysis,
            operation="analysis_synthesis",
            task="synthesis",
            language=language,
        )

    def answer_question(
        self, context: AIChatContext, question: str, *, language: str = "en"
    ) -> ProviderChatAnswer:
        envelope = self._send(
            {
                "model": self.model,
                "instructions": _instructions("chat", language),
                "input": USER_CHAT_PROMPT.format(
                    question=question, context_json=context.model_dump_json()
                ),
                "store": False,
                "reasoning": {"effort": self.reasoning_effort},
                "max_output_tokens": self.max_output_tokens,
                "tools": [
                    {
                        "type": "web_search",
                        "search_context_size": "medium",
                        "user_location": self.search_location,
                    }
                ],
                "max_tool_calls": self.chat_max_tool_calls,
                "include": ["web_search_call.action.sources"],
            },
            operation="chat",
        )
        parts = tuple(
            ChatTextPart(
                text=part["text"],
                citations=tuple(_url_citations(part.get("annotations"))),
            )
            for part in _output_parts(envelope)
        )
        sources = _consulted_sources(envelope)
        logger.info(
            "AI chat web search queries=%s sources=%s",
            _search_queries(envelope),
            sorted(sources),
        )
        return ProviderChatAnswer(parts=parts, sources=frozenset(sources))

    def research_fix(
        self, target: FixResearchTarget
    ) -> tuple[ProviderCVEFixResearch, set[str]]:
        return self._respond(
            USER_RESEARCH_PROMPT.format(context_json=target.model_dump_json()),
            ProviderCVEFixResearch,
            operation="fix_research",
            task="research",
            language="en",
            schema_name="cve_fix_research",
            tools={
                "tools": [{"type": "web_search", "search_context_size": "medium"}],
                "max_tool_calls": self.research_max_tool_calls,
                "include": ["web_search_call.action.sources"],
            },
        )

    def _complete(
        self,
        user_prompt: str,
        response_schema: type[_ProviderResponseT],
        *,
        operation: str,
        task: str,
        language: str,
        repair: bool = False,
        schema_name: str = "scan_ai_analysis",
    ) -> _ProviderResponseT:
        parsed, _ = self._respond(
            user_prompt,
            response_schema,
            operation=operation,
            task=task,
            language=language,
            repair=repair,
            schema_name=schema_name,
        )
        return parsed

    def _respond(
        self,
        user_prompt: str,
        response_schema: type[_ProviderResponseT],
        *,
        operation: str,
        task: str,
        language: str,
        repair: bool = False,
        schema_name: str = "scan_ai_analysis",
        tools: dict[str, object] | None = None,
    ) -> tuple[_ProviderResponseT, set[str]]:
        payload = {
            "model": self.model,
            "instructions": _instructions(task, language, repair=repair),
            "input": user_prompt,
            "store": False,
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": self.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                }
            },
            **(tools or {}),
        }
        envelope = self._send(payload, operation=operation)
        try:
            decoded = json.loads(_output_text(envelope))
            return response_schema.model_validate(decoded), _consulted_sources(
                envelope
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AIProviderError(
                "invalid_provider_response", retryable=False
            ) from exc

    def _send(
        self, payload: dict[str, object], *, operation: str
    ) -> dict[str, object]:
        try:
            response = self._post(payload, operation=operation)
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", retryable=True) from exc
        except httpx.RequestError as exc:
            raise AIProviderError("provider_unavailable", retryable=True) from exc

        if response.status_code >= 400:
            raise _http_error(response)

        try:
            envelope = response.json()
        except ValueError as exc:
            raise AIProviderError(
                "invalid_provider_response", retryable=False
            ) from exc
        if not isinstance(envelope, dict):
            raise AIProviderError("invalid_provider_response", retryable=False)
        return envelope

    def _post(self, payload: dict[str, object], *, operation: str) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        try:
            if self.client is not None:
                response = self.client.post(
                    OPENAI_RESPONSES_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        OPENAI_RESPONSES_URL, headers=headers, json=payload
                    )
        except httpx.TimeoutException:
            self._usage_events.append(
                ProviderUsageEvent(
                    operation,
                    self.model,
                    "error",
                    latency_ms=_elapsed_ms(started),
                    error_code="provider_timeout",
                )
            )
            raise
        except httpx.RequestError:
            self._usage_events.append(
                ProviderUsageEvent(
                    operation,
                    self.model,
                    "error",
                    latency_ms=_elapsed_ms(started),
                    error_code="provider_unavailable",
                )
            )
            raise
        try:
            response_body = response.json() if response.content else {}
        except ValueError:
            response_body = {}
        if not isinstance(response_body, dict):
            response_body = {}
        usage = response_body.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        input_details = usage.get("input_tokens_details")
        output_details = usage.get("output_tokens_details")
        self._usage_events.append(
            ProviderUsageEvent(
                operation,
                self.model,
                "success" if response.status_code < 400 else "error",
                _int_or_none(usage.get("input_tokens")),
                _int_or_none(usage.get("output_tokens")),
                _int_or_none(usage.get("total_tokens")),
                _elapsed_ms(started),
                response.status_code,
                response.headers.get("x-request-id")
                or (
                    response_body.get("id")
                    if isinstance(response_body.get("id"), str)
                    else None
                ),
                None if response.status_code < 400 else f"http_{response.status_code}",
                _int_or_none(
                    input_details.get("cached_tokens")
                    if isinstance(input_details, dict)
                    else None
                ),
                _int_or_none(
                    output_details.get("reasoning_tokens")
                    if isinstance(output_details, dict)
                    else None
                ),
            )
        )
        return response


def _consulted_sources(envelope: dict[str, object]) -> set[str]:
    urls: set[str] = set()
    output = envelope.get("output")
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict) or item.get("type") != "web_search_call":
            continue
        action = item.get("action")
        sources = action.get("sources") if isinstance(action, dict) else None
        for source in sources if isinstance(sources, list) else []:
            url = source.get("url") if isinstance(source, dict) else None
            if isinstance(url, str):
                urls.add(url)
    return urls


def _output_parts(envelope: dict[str, object]) -> list[dict[str, object]]:
    status = envelope.get("status")
    if status == "incomplete":
        details = envelope.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else None
        if reason == "content_filter":
            raise AIProviderError("provider_refused", retryable=False)
        raise AIProviderError("provider_output_truncated", retryable=False)
    if status != "completed":
        raise AIProviderError("invalid_provider_response", retryable=False)
    parts: list[dict[str, object]] = []
    output = envelope.get("output")
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise AIProviderError("provider_refused", retryable=False)
            if part.get("type") == "output_text" and isinstance(
                part.get("text"), str
            ):
                parts.append(part)
    if not "".join(str(part["text"]) for part in parts).strip():
        raise AIProviderError("invalid_provider_response", retryable=False)
    return parts


def _output_text(envelope: dict[str, object]) -> str:
    return "".join(str(part["text"]) for part in _output_parts(envelope))


def _url_citations(annotations: object) -> list[UrlCitation]:
    citations = []
    for annotation in annotations if isinstance(annotations, list) else []:
        if not isinstance(annotation, dict):
            continue
        start = annotation.get("start_index")
        end = annotation.get("end_index")
        url = annotation.get("url")
        if (
            annotation.get("type") == "url_citation"
            and isinstance(start, int)
            and isinstance(end, int)
            and isinstance(url, str)
        ):
            citations.append(UrlCitation(start=start, end=end, url=url))
    return citations


def _search_queries(envelope: dict[str, object]) -> list[str]:
    queries: list[str] = []
    output = envelope.get("output")
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict) or item.get("type") != "web_search_call":
            continue
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        values = action.get("queries")
        if isinstance(values, list):
            queries.extend(value for value in values if isinstance(value, str))
        elif isinstance(action.get("query"), str):
            queries.append(action["query"])
    return queries


@cache
def _instruction_file(name: str) -> str:
    return (_INSTRUCTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _instructions(task: str, language: str, *, repair: bool = False) -> str:
    files = ["voice", task, *(["repair"] if repair else [])]
    return "\n\n".join(
        [
            *(_instruction_file(name) for name in files),
            f"Write all prose in {_language_name(language)}.",
        ]
    )


def _coverage_notice(context: ScanAIContext) -> str:
    if context.evidence_completeness == "complete":
        return ""
    if context.evidence_completeness == "unknown":
        return (
            "Coverage limit: this scan does not report whether every check "
            "finished. A missing finding is not evidence that a vulnerability "
            "is absent.\n\n"
        )
    stop_reason = {
        "operator": "An operator stopped the scan early.",
        "timeout": "A time limit stopped the scan.",
        "error": "An error stopped the scan early.",
    }.get(context.stopped_by, "Some results may be missing.")
    return (
        "Coverage limit: this scan is partial. "
        f"{stop_reason} A missing finding is not evidence that "
        "a vulnerability is absent.\n\n"
    )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _language_name(language: str) -> str:
    return {"en": "English", "pt-BR": "Brazilian Portuguese", "ru": "Russian"}.get(
        language, "English"
    )


def _writing_guidance(violation_codes: tuple[str, ...]) -> str:
    guidance_by_code = {
        "too_long": "keep each field within its character limit",
        "markup": "remove Markdown, HTML, and URLs",
        "raw_identifier": "remove raw IP addresses, MAC addresses, and CVE IDs",
        "safety_certification": (
            "do not describe a network, machine, or service as safe, secure, "
            "protected, or clean"
        ),
        "retired_vocabulary": (
            "replace finding, issue, and weakness with vulnerability, and replace "
            "device, host, endpoint, and asset with machine"
        ),
        "banned_pattern": "remove promotional or banned phrases",
        "punctuation": (
            "remove em dashes, en dashes, semicolons, exclamation marks, "
            "and parentheses"
        ),
        "sentence_too_long": "use sentences with no more than 25 words",
        "too_many": "return no more than three uncertainties",
        "analysis contains an unknown reference": (
            "use only finding_N and machine_N references present in the supplied "
            "context, including in prose"
        ),
        "analysis contains duplicate finding references": (
            "include no more than one important finding explanation per finding_ref"
        ),
        "analysis omits a KEV finding from actions": (
            "include an action referencing every supplied finding marked is_kev=true"
        ),
    }
    corrections = {
        guidance_by_code[code.rsplit(":", 1)[-1]]
        for code in violation_codes
        if code.rsplit(":", 1)[-1] in guidance_by_code
    }
    return "; ".join(sorted(corrections)) or (
        "follow all writing rules in the system instructions"
    )


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _error_code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else None


def _http_error(response: httpx.Response) -> AIProviderError:
    status_code = response.status_code
    error_code = _error_code(response)
    if status_code == 413 or error_code == "context_length_exceeded":
        return AIProviderError("provider_context_too_large", retryable=False)
    if status_code in {401, 403}:
        return AIProviderError("provider_authentication_failed", retryable=False)
    if status_code == 429:
        if error_code == "insufficient_quota":
            return AIProviderError("provider_quota_exceeded", retryable=False)
        return AIProviderError(
            "provider_rate_limited",
            retryable=True,
            retry_after_seconds=_retry_after_seconds(response),
        )
    if status_code == 408:
        return AIProviderError("provider_timeout", retryable=True)
    if status_code >= 500:
        return AIProviderError("provider_unavailable", retryable=True)
    return AIProviderError("provider_request_rejected", retryable=False)


_DURATION_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)(ms|s|m|h)")


def _retry_after_seconds(response: httpx.Response) -> int:
    retry_after = response.headers.get("retry-after")
    if retry_after and re.fullmatch(r"\s*[0-9]+(?:\.[0-9]+)?\s*", retry_after):
        return max(1, math.ceil(float(retry_after)))
    reset = response.headers.get("x-ratelimit-reset-requests") or response.headers.get(
        "x-ratelimit-reset-tokens"
    )
    if reset:
        parts = _DURATION_PART.findall(reset.strip())
        if parts and "".join(value + unit for value, unit in parts) == reset.strip():
            multiplier = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
            seconds = sum(float(value) * multiplier[unit] for value, unit in parts)
            return max(1, math.ceil(seconds))
    return 60


def ai_is_available(settings: Settings) -> bool:
    key = settings.ai_api_key
    value = (
        key.get_secret_value()
        if key is not None and hasattr(key, "get_secret_value")
        else str(key or "")
    )
    return (
        settings.ai_enabled
        and bool(value.strip())
    )


def build_ai_provider(settings: Settings) -> OpenAIResponsesProvider | None:
    if not ai_is_available(settings):
        return None
    assert settings.ai_api_key is not None
    key = (
        settings.ai_api_key.get_secret_value()
        if hasattr(settings.ai_api_key, "get_secret_value")
        else str(settings.ai_api_key)
    )
    return OpenAIResponsesProvider(
        api_key=key,
        model=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
        max_output_tokens=settings.ai_max_output_tokens,
        reasoning_effort=settings.ai_reasoning_effort,
        research_max_tool_calls=settings.ai_research_max_tool_calls,
        chat_max_tool_calls=settings.ai_chat_max_tool_calls,
        search_location={
            "type": "approximate",
            **(
                {"country": settings.ai_search_country}
                if settings.ai_search_country
                else {}
            ),
            **(
                {"timezone": settings.ai_search_timezone}
                if settings.ai_search_timezone
                else {}
            ),
        },
    )
