from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from api.models.persistence import (
    DeviceRecord,
    EnrichmentJobRecord,
    FindingRecord,
    PortRecord,
    ServiceRecord,
)
from api.schemas.scan import Finding
from api.services.epss import EpssClient, upsert_epss_record
from api.services.kev import KevClient, upsert_kev_record
from api.services.nvd import NvdClient, parse_nvd_matches
from api.services.persistence import upsert_finding
from api.services.risk import refresh_risk_snapshot


def claim_pending_enrichment_jobs(
    session: Session,
    *,
    batch_size: int,
) -> list[EnrichmentJobRecord]:
    statement = (
        select(EnrichmentJobRecord)
        .where(EnrichmentJobRecord.status == "pending")
        .order_by(EnrichmentJobRecord.created_at, EnrichmentJobRecord.id)
        .limit(batch_size)
    )
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    jobs = session.exec(statement).all()
    now = datetime.now(timezone.utc)
    for job in jobs:
        job.status = "running"
        job.attempts += 1
        job.started_at = now
        job.completed_at = None
        job.last_error = None
        session.add(job)
    session.commit()
    for job in jobs:
        session.refresh(job)
    return jobs


def process_claimed_enrichment_job(
    session: Session,
    job: EnrichmentJobRecord,
    *,
    client: NvdClient | None = None,
    kev_client: KevClient | None = None,
    epss_client: EpssClient | None = None,
) -> None:
    client = client or NvdClient()
    kev_client = kev_client or KevClient()
    epss_client = epss_client or EpssClient()
    try:
        if job.job_type == "nvd_cpe":
            _process_cpe_job(session, client, job)
        elif job.job_type == "nvd_cve":
            _process_cve_job(session, client, job)
        elif job.job_type == "kev_cve":
            _process_kev_job(session, kev_client, job)
        elif job.job_type == "epss_cve":
            _process_epss_job(session, epss_client, job)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = None
        session.add(job)
        session.commit()
    except Exception as exc:
        session.rollback()
        managed_job = session.get(EnrichmentJobRecord, job.id)
        if managed_job is None:
            raise
        managed_job.status = "failed"
        managed_job.completed_at = datetime.now(timezone.utc)
        managed_job.last_error = str(exc)
        session.add(managed_job)
        session.commit()


def process_pending_enrichment_jobs(
    session: Session,
    *,
    batch_size: int = 10,
    client: NvdClient | None = None,
    kev_client: KevClient | None = None,
    epss_client: EpssClient | None = None,
) -> int:
    jobs = claim_pending_enrichment_jobs(session, batch_size=batch_size)
    if not jobs:
        return 0

    resolved_client = client or NvdClient()
    resolved_kev_client = kev_client or KevClient()
    resolved_epss_client = epss_client or EpssClient()
    for job in jobs:
        process_claimed_enrichment_job(
            session,
            job,
            client=resolved_client,
            kev_client=resolved_kev_client,
            epss_client=resolved_epss_client,
        )
    return len(jobs)


def _process_cpe_job(
    session: Session,
    client: NvdClient,
    job: EnrichmentJobRecord,
) -> None:
    if job.port_id is None:
        return
    port_record = session.get(PortRecord, job.port_id)
    if port_record is None:
        return
    device = session.get(DeviceRecord, port_record.device_id)
    service = session.exec(
        select(ServiceRecord).where(ServiceRecord.port_id == port_record.id)
    ).first()
    payload = client.query_by_cpe(session, job.target_value)
    for match in parse_nvd_matches(payload):
        finding = Finding(
            ip=device.ip if device is not None else None,
            port=port_record.port,
            protocol=port_record.protocol,  # type: ignore[arg-type]
            service=service.name if service is not None else None,
            source="nvd_enrichment",
            source_script=None,
            cve_id=match["cve_id"],
            cvss_score=match["cvss_score"],
            severity=match["severity"],  # type: ignore[arg-type]
            title=f"NVD matched observed CPE to {match['cve_id']}",
            description=match["description"],
            recommendation=(
                "Validate the affected software version and patch or mitigate "
                "the service if exposure is confirmed."
            ),
            evidence=(
                f"NVD returned {match['cve_id']} for observed CPE {job.target_value} "
                f"on {device.ip if device is not None else 'unknown host'}."
            ),
            references=match["references"],
        )
        upsert_finding(
            session,
            scan_id=job.scan_id,
            finding=finding,
            device_record=device,
            port_record=port_record,
            confidence="probable",
            extra_source="nvd",
            references=match["references"],
            evidence_suffix=f"NVD correlation via CPE {job.target_value}.",
        )
    session.commit()


def _process_cve_job(
    session: Session,
    client: NvdClient,
    job: EnrichmentJobRecord,
) -> None:
    if job.finding_id is None:
        return
    finding_record = session.get(FindingRecord, job.finding_id)
    if finding_record is None or finding_record.cve_id is None:
        return
    payload = client.query_by_cve(session, job.target_value)
    matches = parse_nvd_matches(payload)
    if not matches:
        return
    match = matches[0]
    finding_record.confidence = "confirmed"
    finding_record.cvss_score = match["cvss_score"] or finding_record.cvss_score
    finding_record.severity = match["severity"]
    finding_record.references_json = sorted(
        set(finding_record.references_json).union(match["references"])
    )
    finding_record.source_labels_json = sorted(
        set(finding_record.source_labels_json).union({"nvd"})
    )
    if "NVD validated this CVE." not in finding_record.evidence:
        finding_record.evidence = (
            f"{finding_record.evidence} | NVD validated this CVE."
        )
    finding_record.updated_at = datetime.now(timezone.utc)
    session.add(finding_record)
    refresh_risk_snapshot(session, finding_record)
    session.commit()


def _process_kev_job(
    session: Session,
    client: KevClient,
    job: EnrichmentJobRecord,
) -> None:
    finding_record = _load_finding_for_cve_job(session, job)
    if finding_record is None:
        return

    payload = client.query_by_cve(session, job.target_value)
    kev_record = upsert_kev_record(
        session,
        cve_id=job.target_value,
        payload=payload,
    )
    if kev_record is not None:
        finding_record.references_json = sorted(
            set(finding_record.references_json).union(
                {"https://www.cisa.gov/known-exploited-vulnerabilities-catalog"}
            )
        )
        finding_record.source_labels_json = sorted(
            set(finding_record.source_labels_json).union({"kev"})
        )
        if "KEV catalog lists this CVE." not in finding_record.evidence:
            finding_record.evidence = (
                f"{finding_record.evidence} | KEV catalog lists this CVE."
            )
    finding_record.updated_at = datetime.now(timezone.utc)
    session.add(finding_record)
    refresh_risk_snapshot(session, finding_record)
    session.commit()


def _process_epss_job(
    session: Session,
    client: EpssClient,
    job: EnrichmentJobRecord,
) -> None:
    finding_record = _load_finding_for_cve_job(session, job)
    if finding_record is None:
        return

    payload = client.query_by_cve(session, job.target_value)
    epss_record = upsert_epss_record(
        session,
        cve_id=job.target_value,
        payload=payload,
    )
    if epss_record is not None:
        finding_record.source_labels_json = sorted(
            set(finding_record.source_labels_json).union({"epss"})
        )
        if "EPSS score recorded for this CVE." not in finding_record.evidence:
            finding_record.evidence = (
                f"{finding_record.evidence} | EPSS score recorded for this CVE."
            )
    finding_record.updated_at = datetime.now(timezone.utc)
    session.add(finding_record)
    refresh_risk_snapshot(session, finding_record)
    session.commit()


def _load_finding_for_cve_job(
    session: Session,
    job: EnrichmentJobRecord,
) -> FindingRecord | None:
    if job.finding_id is None:
        return None
    finding_record = session.get(FindingRecord, job.finding_id)
    if finding_record is None or finding_record.cve_id is None:
        return None
    return finding_record
