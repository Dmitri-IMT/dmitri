from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from api.schemas.ai import AIChatResponse
from api.services.ai.chat import materialize_chat_response


class AIQuestionProvider(Protocol):
    """Small provider contract used by interactive, read-only AI features."""

    def answer_question(
        self, context: Mapping[str, object], question: str, language: str = "en"
    ) -> object: ...


class AIOrchestrator:
    """Coordinate a grounded question without coupling routes to Groq."""

    def __init__(self, provider: AIQuestionProvider) -> None:
        self._provider = provider

    def answer_question(
        self,
        *,
        context: Mapping[str, object],
        question: str,
        finding_references: Mapping[str, UUID],
        language: str = "en",
    ) -> AIChatResponse:
        try:
            provider_response = self._provider.answer_question(
                context, question, language=language
            )
        except TypeError as exc:
            if "language" not in str(exc):
                raise
            provider_response = self._provider.answer_question(context, question)
        return materialize_chat_response(provider_response, finding_references)
