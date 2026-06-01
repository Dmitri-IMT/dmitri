from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlmodel import Session

from api.core.config import get_settings
from api.models.persistence import KevCacheRecord, KevRecord


class KevClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.kev_api_base_url
        self.ttl = timedelta(hours=settings.kev_cache_ttl_hours)

    def query_by_cve(self, session: Session, cve_id: str) -> dict[str, Any] | None:
        normalized_cve = cve_id.upper()
        cached = session.get(KevCacheRecord, normalized_cve)
        now = datetime.now(timezone.utc)
        if cached is not None and cached.expires_at >= now:
            return cached.response_json or None

        payload = self._fetch_from_remote(normalized_cve)
        expires_at = now + self.ttl
        cache_payload = _json_safe_payload(payload)
        if cached is None:
            cached = KevCacheRecord(
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
            response = client.get(self.base_url)
            response.raise_for_status()
            payload = response.json()
        return parse_kev_record(payload, cve_id)


def parse_kev_record(payload: dict[str, Any], cve_id: str) -> dict[str, Any] | None:
    for item in payload.get("vulnerabilities", []):
        if item.get("cveID", "").upper() != cve_id.upper():
            continue
        return {
            "cve_id": cve_id.upper(),
            "date_added": _parse_date(item.get("dateAdded")),
            "known_ransomware": _parse_bool(item.get("knownRansomwareCampaignUse")),
            "required_action": item.get("requiredAction"),
            "raw_json": item,
        }
    return None


def upsert_kev_record(
    session: Session,
    *,
    cve_id: str,
    payload: dict[str, Any] | None,
) -> KevRecord | None:
    normalized_cve = cve_id.upper()
    existing = session.get(KevRecord, normalized_cve)
    if payload is None:
        if existing is not None:
            existing.updated_at = datetime.now(timezone.utc)
            session.add(existing)
            session.flush()
        return existing

    now = datetime.now(timezone.utc)
    if existing is None:
        existing = KevRecord(
            cve_id=normalized_cve,
            date_added=payload.get("date_added"),
            known_ransomware=bool(payload.get("known_ransomware")),
            required_action=payload.get("required_action"),
            raw_json=payload.get("raw_json"),
            fetched_at=now,
            updated_at=now,
        )
        session.add(existing)
        session.flush()
        return existing

    existing.date_added = payload.get("date_added")
    existing.known_ransomware = bool(payload.get("known_ransomware"))
    existing.required_action = payload.get("required_action")
    existing.raw_json = payload.get("raw_json")
    existing.fetched_at = now
    existing.updated_at = now
    session.add(existing)
    session.flush()
    return existing


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return value.strip().lower() in {"known", "yes", "true", "1"}


def _json_safe_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    safe_payload = dict(payload)
    date_added = safe_payload.get("date_added")
    if isinstance(date_added, datetime):
        safe_payload["date_added"] = date_added.date().isoformat()
    return safe_payload
