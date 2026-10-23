from __future__ import annotations

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlmodel import Session, select

from api.core.config import Settings
from api.models.persistence import (
    AIFixRecord,
    CPERecord,
    FindingRecord,
    KevRecord,
    NvdCacheRecord,
    ServiceRecord,
)
from api.schemas.ai import ProviderCVEFixResearch
from api.services.ai.context import (
    AIFixOptionContext,
    FixResearchTarget,
    ScanAIContext,
)
from api.services.ai.openai_responses import AIProviderError
from api.services.ai.providers import FixResearchProvider

logger = logging.getLogger(__name__)

FIX_RESEARCH_VERSION = "1"
MAX_PARALLEL_RESEARCH = 5

_EFFORT_ORDER = ("setting_change", "update", "workaround", "replace", "ask_vendor")
_WRAPPED_LINK = re.compile(r"\(\s*\[[^\]]*\]\([^)]*\)\s*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([.,:])")


@dataclass
class _ResearchItem:
    target: FixResearchTarget
    cache_key: str
    kev_fingerprint: str
    nvd_last_modified: str | None
    finding_refs: list[str] = field(default_factory=list)
    record: dict[str, object] | None = None


def attach_fix_records(
    session: Session,
    context: ScanAIContext,
    provider: FixResearchProvider,
    *,
    settings: Settings,
    now: datetime,
) -> None:
    items = _research_items(session, context)
    if not items:
        return
    cached = {
        row.cache_key: row
        for row in session.exec(
            select(AIFixRecord).where(AIFixRecord.cache_key.in_(list(items)))
        ).all()
    }
    missing = []
    for key, item in items.items():
        row = cached.get(key)
        if row is not None and _is_current(row, item, now):
            item.record = row.record_json
        else:
            missing.append(item)

    rate_limited: AIProviderError | None = None
    if missing:
        with ThreadPoolExecutor(
            max_workers=min(len(missing), MAX_PARALLEL_RESEARCH)
        ) as pool:
            futures = [
                (item, pool.submit(provider.research_fix, item.target))
                for item in missing
            ]
            for item, future in futures:
                try:
                    research, sources = future.result()
                except AIProviderError as exc:
                    if exc.code == "provider_rate_limited":
                        rate_limited = exc
                    logger.warning(
                        "Fix research failed cve=%s code=%s",
                        item.target.cve_id,
                        exc.code,
                    )
                    continue
                record = sourced_fix_record(research, sources)
                if record is None:
                    logger.info(
                        "Fix research kept no sourced option cve=%s",
                        item.target.cve_id,
                    )
                    continue
                item.record = record
                _save(session, cached.get(item.cache_key), item, settings, now)
        session.commit()
    if rate_limited is not None:
        raise rate_limited

    by_ref = {finding.finding_ref: finding for finding in context.top_findings}
    for item in items.values():
        if item.record is None:
            continue
        for ref in item.finding_refs:
            finding = by_ref[ref]
            finding.version_affected = item.record["version_affected"]
            finding.fix_options = [
                AIFixOptionContext(
                    effort=option["effort"],
                    who=option["who"],
                    steps=option["steps"],
                    fixed_version=option["fixed_version"],
                    fixes_fully=option["fixes_fully"],
                    source_name=option["source_name"],
                )
                for option in item.record["options"]
            ]


def sourced_fix_record(
    research: ProviderCVEFixResearch, consulted_urls: set[str]
) -> dict[str, object] | None:
    consulted = {clean_source_url(url) for url in consulted_urls} - {None}
    options = []
    for option in research.options:
        url = clean_source_url(option.source_url)
        if url is None or url not in consulted:
            continue
        steps = [step for step in (_plain(value) for value in option.steps) if step]
        source_name = _plain(option.source_name)
        if not steps or not source_name:
            continue
        options.append(
            {
                "effort": option.effort,
                "who": option.who,
                "steps": steps,
                "fixed_version": (
                    _plain(option.fixed_version) or None
                    if option.fixed_version is not None
                    else None
                ),
                "fixes_fully": option.fixes_fully,
                "source_name": source_name,
                "source_url": url,
            }
        )
    if not options:
        return None
    options.sort(
        key=lambda option: (
            not option["fixes_fully"],
            _EFFORT_ORDER.index(option["effort"]),
        )
    )
    return {"version_affected": research.version_affected, "options": options}


def clean_source_url(url: str) -> str | None:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = urlencode(
        [
            (name, value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
            if name != "utm_source"
        ]
    )
    return urlunsplit(
        (parts.scheme, parts.netloc.lower(), parts.path, query, "")
    )


def _plain(value: str) -> str:
    text = _WRAPPED_LINK.sub("", value)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("", text).replace("**", "")
    return _SPACE_BEFORE_PUNCTUATION.sub(r"\1", " ".join(text.split())).strip()


def _research_items(
    session: Session, context: ScanAIContext
) -> dict[str, _ResearchItem]:
    findings = [
        finding for finding in context.top_findings if finding.cve_id is not None
    ]
    if not findings:
        return {}
    finding_ids = {
        finding.finding_ref: context._finding_ids_by_ref[finding.finding_ref]
        for finding in findings
    }
    products = _observed_products(session, list(finding_ids.values()))
    cve_ids = {finding.cve_id.upper() for finding in findings}
    kev_by_cve = {
        row.cve_id.upper(): row
        for row in session.exec(
            select(KevRecord).where(KevRecord.cve_id.in_(cve_ids))
        ).all()
    }
    nvd_by_cve = {
        row.query_value.upper(): row
        for row in session.exec(
            select(NvdCacheRecord).where(
                NvdCacheRecord.query_key.in_([f"cve:{cve}" for cve in cve_ids])
            )
        ).all()
    }
    items: dict[str, _ResearchItem] = {}
    for finding in findings:
        cve_id = finding.cve_id.upper()
        service, product, version = products.get(
            finding_ids[finding.finding_ref], (None, None, None)
        )
        key = hashlib.sha256(
            f"{FIX_RESEARCH_VERSION}|{cve_id}|{product or ''}|{version or ''}".encode()
        ).hexdigest()
        if key not in items:
            kev = kev_by_cve.get(cve_id)
            items[key] = _ResearchItem(
                target=FixResearchTarget(
                    cve_id=cve_id,
                    product=product,
                    version=version,
                    service=service,
                    severity=finding.severity,
                    cvss_score=finding.cvss_score,
                    is_kev=finding.is_kev,
                    kev_required_action=(
                        kev.required_action if kev is not None else None
                    ),
                    epss_score=finding.epss_score,
                ),
                cache_key=key,
                kev_fingerprint=_kev_fingerprint(kev),
                nvd_last_modified=_nvd_last_modified(nvd_by_cve.get(cve_id)),
            )
        items[key].finding_refs.append(finding.finding_ref)
    return items


def _observed_products(
    session: Session, finding_ids: list[UUID]
) -> dict[UUID, tuple[str | None, str | None, str | None]]:
    services = {
        finding_id: (name, version)
        for finding_id, name, version in session.exec(
            select(FindingRecord.finding_id, ServiceRecord.name, ServiceRecord.version)
            .join(ServiceRecord, ServiceRecord.port_id == FindingRecord.port_id)
            .where(FindingRecord.finding_id.in_(finding_ids))
        ).all()
    }
    cpes: dict[UUID, list[str]] = {}
    for finding_id, cpe in session.exec(
        select(FindingRecord.finding_id, CPERecord.cpe)
        .join(CPERecord, CPERecord.port_id == FindingRecord.port_id)
        .where(FindingRecord.finding_id.in_(finding_ids))
    ).all():
        cpes.setdefault(finding_id, []).append(cpe)

    products = {}
    for finding_id in finding_ids:
        name, banner = services.get(finding_id, (None, None))
        parsed = sorted(
            (
                product
                for product in (_cpe_product(cpe) for cpe in cpes.get(finding_id, []))
                if product is not None
            ),
            key=lambda product: (product[1] is None, product),
        )
        if parsed:
            product, version = parsed[0]
        else:
            product, version = _normalize(name), _normalize(banner)
        products[finding_id] = (_normalize(name), product, version)
    return products


def _cpe_product(cpe: str) -> tuple[str, str | None] | None:
    if cpe.startswith("cpe:2.3:"):
        parts = cpe.split(":")[2:]
    elif cpe.startswith("cpe:/"):
        parts = cpe[5:].split(":")
    else:
        return None
    if len(parts) < 3 or parts[0] != "a" or not parts[1] or not parts[2]:
        return None
    version = parts[3] if len(parts) > 3 and parts[3] not in {"", "*", "-"} else None
    product = _normalize(f"{parts[1]} {parts[2]}".replace("_", " "))
    if product is None:
        return None
    return product, _normalize(version)


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.lower().split())[:160]
    return text or None


def _kev_fingerprint(kev: KevRecord | None) -> str:
    if kev is None:
        return "none"
    date_added = kev.date_added.isoformat() if kev.date_added is not None else ""
    return f"{date_added}|{kev.known_ransomware}|{kev.required_action or ''}"


def _nvd_last_modified(row: NvdCacheRecord | None) -> str | None:
    if row is None:
        return None
    vulnerabilities = row.response_json.get("vulnerabilities")
    if not isinstance(vulnerabilities, list) or not vulnerabilities:
        return None
    first = vulnerabilities[0]
    cve = first.get("cve") if isinstance(first, dict) else None
    value = cve.get("lastModified") if isinstance(cve, dict) else None
    return value if isinstance(value, str) else None


def _is_current(row: AIFixRecord, item: _ResearchItem, now: datetime) -> bool:
    return (
        row.expires_at > now
        and row.kev_fingerprint == item.kev_fingerprint
        and row.nvd_last_modified == item.nvd_last_modified
    )


def _save(
    session: Session,
    row: AIFixRecord | None,
    item: _ResearchItem,
    settings: Settings,
    now: datetime,
) -> None:
    assert item.record is not None
    has_fix = any(option["fixes_fully"] for option in item.record["options"])
    expires_at = now + timedelta(
        days=(
            settings.ai_fix_record_ttl_fixed_days
            if has_fix
            else settings.ai_fix_record_ttl_unfixed_days
        )
    )
    if row is None:
        row = AIFixRecord(
            cache_key=item.cache_key,
            cve_id=item.target.cve_id,
            product=item.target.product or "",
            version=item.target.version or "",
            research_version=FIX_RESEARCH_VERSION,
            record_json=item.record,
            has_fix=has_fix,
            kev_fingerprint=item.kev_fingerprint,
            nvd_last_modified=item.nvd_last_modified,
            created_at=now,
            expires_at=expires_at,
        )
    else:
        row.record_json = item.record
        row.has_fix = has_fix
        row.kev_fingerprint = item.kev_fingerprint
        row.nvd_last_modified = item.nvd_last_modified
        row.created_at = now
        row.expires_at = expires_at
    session.add(row)
