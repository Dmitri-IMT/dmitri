from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlmodel import Session

from api.core.config import get_settings
from api.models.persistence import EpssCacheRecord, EpssRecord


class EpssClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.epss_api_base_url
        self.ttl = timedelta(hours=settings.epss_cache_ttl_hours)

    def query_by_cve(self, session: Session, cve_id: str) -> dict[str, Any] | None:
        normalized_cve = cve_id.upper()
        cached = session.get(EpssCacheRecord, normalized_cve)
        now = datetime.now(timezone.utc)
        if cached is not None and cached.expires_at >= now:
            return cached.response_json or None

        payload = self._fetch_from_remote(normalized_cve)
        expires_at = now + self.ttl
        cache_payload = _json_safe_payload(payload)
        if cached is None:
            cached = EpssCacheRecord(
                cve_id=normalized_cve,
                response_json=cache_payload,
                fetched_at=now,
                expires_at=expires_at,
            )
            session.add(cached)
        else:
            cached.response_json = cache_payload
            cached.fetched_at = now
            cached.expires_at = expires_at
        session.commit()
        return payload

    def _fetch_from_remote(self, cve_id: str) -> dict[str, Any] | None:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(self.base_url, params={"cve": cve_id})
            response.raise_for_status()
            payload = response.json()
        return parse_epss_record(payload, cve_id)


def parse_epss_record(payload: dict[str, Any], cve_id: str) -> dict[str, Any] | None:
    records = payload.get("data", [])
    if not records:
        return None
    record = next(
        (item for item in records if item.get("cve", "").upper() == cve_id.upper()),
        None,
    )
    if record is None:
        return None
    scored_at = _parse_scored_at(record.get("date"))
    return {
        "cve_id": cve_id.upper(),
        "epss_score": float(record["epss"]),
        "percentile": (
            float(record["percentile"])
            if record.get("percentile") is not None
            else None
        ),
        "scored_at": scored_at,
        "raw_json": record,
    }


def upsert_epss_record(
    session: Session,
    *,
    cve_id: str,
    payload: dict[str, Any] | None,
) -> EpssRecord | None:
    normalized_cve = cve_id.upper()
    existing = session.get(EpssRecord, normalized_cve)
    if payload is None:
        if existing is not None:
            existing.updated_at = datetime.now(timezone.utc)
            session.add(existing)
            session.flush()
        return existing

    now = datetime.now(timezone.utc)
    if existing is None:
        existing = EpssRecord(
            cve_id=normalized_cve,
            epss_score=float(payload["epss_score"]),
            percentile=payload.get("percentile"),
            scored_at=payload.get("scored_at"),
            raw_json=payload.get("raw_json"),
            fetched_at=now,
            updated_at=now,
        )
        session.add(existing)
        session.flush()
        return existing

    existing.epss_score = float(payload["epss_score"])
    existing.percentile = payload.get("percentile")
    existing.scored_at = payload.get("scored_at")
    existing.raw_json = payload.get("raw_json")
    existing.fetched_at = now
    existing.updated_at = now
    session.add(existing)
    session.flush()
    return existing


def _parse_scored_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _json_safe_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    safe_payload = dict(payload)
    scored_at = safe_payload.get("scored_at")
    if isinstance(scored_at, datetime):
        safe_payload["scored_at"] = scored_at.date().isoformat()
    return safe_payload
