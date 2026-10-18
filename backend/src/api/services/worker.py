from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from api.core.config import get_settings
from api.db.session import get_session
from api.services.ai.groq import GroqProvider, build_ai_provider
from api.services.ai.jobs import process_ready_ai_analyses
from api.services.commands import sweep_stale_commands
from api.services.enrichment import process_pending_enrichment_jobs
from api.services.nvd import NvdClient
from api.services.release_catalog import refresh_release_catalog

logger = logging.getLogger(__name__)
_last_catalog_refresh = 0.0


def _poll_forever(tick: Callable[[], int], interval: float) -> None:
    while True:
        try:
            if tick() == 0:
                time.sleep(interval)
        except Exception:
            logger.exception("worker loop failed; sleeping before retry")
            time.sleep(interval)


def run_worker_loop() -> None:
    settings = get_settings()
    poll_interval = settings.enrichment_poll_interval_seconds
    batch_size = settings.enrichment_batch_size

    logger.info(
        "starting enrichment worker poll_interval=%s batch_size=%s",
        poll_interval,
        batch_size,
    )
    nvd_client = NvdClient()
    _poll_forever(
        lambda: run_worker_once(batch_size=batch_size, nvd_client=nvd_client),
        poll_interval,
    )


def run_ai_worker_loop() -> None:
    settings = get_settings()
    provider = build_ai_provider(settings)
    if provider is None:
        return

    poll_interval = settings.ai_poll_interval_seconds
    logger.info("starting AI worker poll_interval=%s", poll_interval)
    _poll_forever(lambda: run_ai_worker_once(provider=provider), poll_interval)


def run_ai_worker_once(*, provider: GroqProvider) -> int:
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


def run_worker_once(
    *,
    batch_size: int | None = None,
    nvd_client: NvdClient | None = None,
) -> int:
    settings = get_settings()
    global _last_catalog_refresh
    resolved_batch_size = batch_size or settings.enrichment_batch_size

    for session in get_session():
        if settings.agent_update_repository_url and time.monotonic() - _last_catalog_refresh >= settings.agent_update_refresh_interval_seconds:
            try:
                refresh_release_catalog(session, settings)
            except Exception:
                logger.exception("agent release catalogue refresh failed; preserving prior catalogue")
                session.rollback()
            finally:
                _last_catalog_refresh = time.monotonic()
        try:
            sweep_stale_commands(session, now=datetime.now(UTC))
        except Exception:
            # The sweep is a janitor, not the point of the tick — a failure here
            # must not stop enrichment from draining its queue.
            logger.exception("stale command sweep failed; continuing")
            session.rollback()
        return process_pending_enrichment_jobs(
            session,
            batch_size=resolved_batch_size,
            client=nvd_client,
        )
    return 0
