from __future__ import annotations

from api.core.config import Settings
from api.services.ai.groq import GroqProvider
from api.services.ai.provider import AIProvider


def ai_is_available(settings: Settings) -> bool:
    return (
        settings.ai_enabled
        and settings.ai_api_key is not None
        and bool(settings.ai_api_key.get_secret_value().strip())
    )


def build_ai_provider(settings: Settings) -> AIProvider | None:
    if not ai_is_available(settings):
        return None
    assert settings.ai_api_key is not None
    return GroqProvider(
        api_key=settings.ai_api_key.get_secret_value(),
        model=settings.ai_model,
        base_url=settings.ai_api_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
        max_output_tokens=settings.ai_max_output_tokens,
        reasoning_effort=settings.ai_reasoning_effort,
    )
