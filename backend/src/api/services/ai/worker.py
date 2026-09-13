from __future__ import annotations

import logging
import time

from api.core.config import get_settings
from api.db.session import get_session
from api.services.ai.factory import ai_is_available, build_ai_provider
from api.services.ai.jobs import process_ready_ai_analyses
from api.services.ai.provider import AIProvider

logger = logging.getLogger(__name__)


def run_ai_worker_loop() -> None:
    settings = get_settings()
    if not ai_is_available(settings):
        return
    provider = build_ai_provider(settings)
    if provider is None:
        return

    poll_interval = settings.ai_poll_interval_seconds
    logger.info("starting AI worker poll_interval=%s", poll_interval)

    while True:
        try:
            processed = run_ai_worker_once(provider=provider)
            if processed == 0:
                time.sleep(poll_interval)
        except Exception:
            logger.exception("AI worker loop failed; sleeping before retry")
            time.sleep(poll_interval)


def run_ai_worker_once(*, provider: AIProvider) -> int:
    settings = get_settings()
    for session in get_session():
        return process_ready_ai_analyses(
            session,
            provider=provider,
            batch_size=1,
            max_findings=settings.ai_max_findings,
            max_attempts=settings.ai_max_attempts,
            retry_delay_seconds=settings.ai_retry_delay_seconds,
            stale_after_seconds=max(settings.ai_timeout_seconds * 2, 60),
        )
    return 0
