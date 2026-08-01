from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from api.core.config import get_settings
from api.db.session import get_session
from api.services.commands import sweep_stale_commands
from api.services.enrichment import process_pending_enrichment_jobs

logger = logging.getLogger(__name__)


def run_worker_loop() -> None:
    settings = get_settings()
    poll_interval = settings.enrichment_poll_interval_seconds
    batch_size = settings.enrichment_batch_size

    logger.info(
        "starting enrichment worker poll_interval=%s batch_size=%s",
        poll_interval,
        batch_size,
    )

    while True:
        try:
            processed = run_worker_once(batch_size=batch_size)
            if processed == 0:
                time.sleep(poll_interval)
        except Exception:
            logger.exception("worker loop failed; sleeping before retry")
            time.sleep(poll_interval)


def run_worker_once(*, batch_size: int | None = None) -> int:
    settings = get_settings()
    resolved_batch_size = batch_size or settings.enrichment_batch_size

    for session in get_session():
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
        )
    return 0
