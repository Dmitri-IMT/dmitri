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
from api.services.nvd import NvdClient, parse_nvd_matches
from api.services.persistence import upsert_finding


def process_pending_enrichment_jobs(session: Session) -> int:
    client = NvdClient()
    jobs = session.exec(
        select(EnrichmentJobRecord).where(EnrichmentJobRecord.status == "pending")
    ).all()
    processed = 0
    for job in jobs:
        processed += 1
        job.status = "running"
        job.attempts += 1
        job.started_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        try:
            if job.job_type == "nvd_cpe":
                _process_cpe_job(session, client, job)
            elif job.job_type == "nvd_cve":
                _process_cve_job(session, client, job)
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.last_error = None
            session.add(job)
            session.commit()
        except Exception as exc:
            job.status = "failed"
            job.last_error = str(exc)
            session.add(job)
            session.commit()
    return processed


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
    session.commit()
