from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

from api.services.ai.prompts import SYSTEM_PROMPT, USER_PROMPT
from api.services.ai.provider import AIProviderError
from api.services.ai.schemas import ScanAIAnalysis, ScanAIContext


class GroqProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_output_tokens: int,
        reasoning_effort: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.reasoning_effort = reasoning_effort
        self.client = client

    def analyze_scan(self, context: ScanAIContext) -> ScanAIAnalysis:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT.format(
                        context_json=context.model_dump_json()
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "scan_ai_analysis",
                    "strict": True,
                    "schema": ScanAIAnalysis.model_json_schema(),
                },
            },
            "max_completion_tokens": self.max_output_tokens,
            "reasoning_effort": self.reasoning_effort,
            "include_reasoning": False,
        }
        try:
            response = self._post(payload)
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", retryable=True) from exc
        except httpx.RequestError as exc:
            raise AIProviderError("provider_unavailable", retryable=True) from exc

        if response.status_code >= 400:
            raise _http_error(response.status_code)

        try:
            envelope = response.json()
            content = envelope["choices"][0]["message"]["content"]
            decoded = json.loads(content)
            return ScanAIAnalysis.model_validate(decoded)
        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            raise AIProviderError("invalid_provider_response", retryable=True) from exc

    def _post(self, payload: dict[str, object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        if self.client is not None:
            return self.client.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(url, headers=headers, json=payload)


def _http_error(status_code: int) -> AIProviderError:
    if status_code in {401, 403}:
        return AIProviderError("provider_authentication_failed", retryable=False)
    if status_code in {400, 422}:
        return AIProviderError("invalid_provider_response", retryable=True)
    if status_code in {408, 499}:
        return AIProviderError("provider_timeout", retryable=True)
    if status_code == 429:
        return AIProviderError("provider_rate_limited", retryable=True)
    if status_code == 498 or status_code >= 500:
        return AIProviderError("provider_unavailable", retryable=True)
    return AIProviderError("provider_request_rejected", retryable=False)
