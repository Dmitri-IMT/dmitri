from __future__ import annotations

from api.schemas.ai import AILanguage

_MESSAGES: dict[str, dict[AILanguage, str]] = {
    "ai_rate_limited": {
        "en": "Temporary AI token limit reached. Try again in about {seconds} seconds.",
        "pt-BR": (
            "Limite temporário de tokens da IA atingido. "
            "Tente novamente em aproximadamente {seconds} segundos."
        ),
        "ru": (
            "Достигнут временный лимит токенов ИИ. "
            "Повторите попытку примерно через {seconds} сек."
        ),
    },
    "ai_daily_limit": {
        "en": "You reached today's limit of {limit} AI questions. Try again tomorrow.",
        "pt-BR": (
            "Você atingiu o limite de hoje de {limit} perguntas à IA. "
            "Tente novamente amanhã."
        ),
        "ru": (
            "Вы исчерпали сегодняшний лимит в {limit} вопросов ИИ. "
            "Попробуйте снова завтра."
        ),
    },
    "ai_context_too_large": {
        "en": "The context is too large. Try a more specific question.",
        "pt-BR": "O contexto é grande demais. Tente uma pergunta mais específica.",
        "ru": "Контекст слишком большой. Задайте более конкретный вопрос.",
    },
}


def chat_api_error_message(
    code: str, *, language: AILanguage, seconds: int = 60, limit: int = 0
) -> str:
    templates = _MESSAGES.get(code)
    if templates is None:
        raise KeyError(code)
    return templates[language].format(seconds=seconds, limit=limit)
