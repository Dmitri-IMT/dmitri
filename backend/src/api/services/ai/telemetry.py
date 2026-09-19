from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlmodel import Session

from api.models.persistence import AIUsageRecord
from api.services.ai.groq import GroqUsageEvent


def drain_provider_usage(provider: object) -> list[GroqUsageEvent]:
    drain = getattr(provider, "drain_usage_events", None)
    return list(drain()) if callable(drain) else []


def persist_usage_events(
    session: Session,
    events: Iterable[GroqUsageEvent],
    *,
    scan_id: UUID | None = None,
    org_id: UUID | None = None,
    user_id: UUID | None = None,
) -> None:
    """Persist only operational usage metadata, never prompts or model output."""
    rows = [
        AIUsageRecord(
            org_id=org_id,
            scan_id=scan_id,
            user_id=user_id,
            operation=event.operation,
            provider="groq",
            model=event.model,
            status=event.status,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            total_tokens=event.total_tokens,
            latency_ms=event.latency_ms,
            http_status=event.http_status,
            request_id=event.request_id,
            error_code=event.error_code,
        )
        for event in events
    ]
    if rows:
        session.add_all(rows)
        session.commit()
