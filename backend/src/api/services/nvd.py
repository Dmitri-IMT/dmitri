from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlmodel import Session, select

from api.core.config import get_settings
from api.models.persistence import NvdCacheRecord


class NvdClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.nvd_api_base_url
        self.api_key = settings.nvd_api_key
        self.ttl = timedelta(hours=settings.nvd_cache_ttl_hours)

    def query_by_cpe(self, session: Session, cpe: str) -> dict[str, Any]:
        return self._query(session, "cpe", cpe, {"cpeName": cpe})

    def query_by_cve(self, session: Session, cve_id: str) -> dict[str, Any]:
        return self._query(session, "cve", cve_id, {"cveId": cve_id})

    def _query(
        self,
        session: Session,
        query_kind: str,
        query_value: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        query_key = f"{query_kind}:{query_value}"
        cached = session.exec(
            select(NvdCacheRecord).where(NvdCacheRecord.query_key == query_key)
        ).first()
        now = datetime.now(timezone.utc)
        if cached is not None and cached.expires_at >= now:
            return cached.response_json

        headers = {"apiKey": self.api_key} if self.api_key else {}
        with httpx.Client(timeout=20.0, headers=headers) as client:
            response = client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()

        expires_at = now + self.ttl
        if cached is None:
            cached = NvdCacheRecord(
                query_key=query_key,
                query_kind=query_kind,
                query_value=query_value,
                response_json=payload,
                fetched_at=now,
                expires_at=expires_at,
            )
            session.add(cached)
        else:
            cached.response_json = payload
            cached.fetched_at = now
            cached.expires_at = expires_at
        session.commit()
        return payload


def parse_nvd_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    vulnerabilities = payload.get("vulnerabilities", [])
    for vulnerability in vulnerabilities:
        cve = vulnerability.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            continue
        descriptions = cve.get("descriptions", [])
        description = next(
            (
                item.get("value")
                for item in descriptions
                if item.get("lang") == "en" and item.get("value")
            ),
            "",
        )
        references = [
            item.get("url")
            for item in cve.get("references", [])
            if item.get("url")
        ]
        metrics = cve.get("metrics", {})
        cvss_score = None
        severity = "medium"
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(key)
            if not entries:
                continue
            cvss_data = entries[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            severity = _severity_from_cvss(cvss_score)
            break
        matches.append(
            {
                "cve_id": cve_id,
                "description": description or "NVD published an advisory for this CPE.",
                "references": references,
                "cvss_score": cvss_score,
                "severity": severity,
            }
        )
    return matches


def _severity_from_cvss(score: float | None) -> str:
    if score is None:
        return "medium"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"
