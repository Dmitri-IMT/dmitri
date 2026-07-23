from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlmodel import Session, select

from api.models.persistence import (
    ArtifactRecord,
    CPERecord,
    EnrichmentJobRecord,
    FindingRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas.scan import Finding, Host, Port, ScanResult
from api.services.hosts import upsert_hosts_for_scan
from api.services.risk import refresh_risk_snapshot


def persist_scan(session: Session, scan: ScanResult) -> ScanRecord:
    existing = session.get(ScanRecord, scan.scan_id)
    if existing is not None:
        return existing

    scan_record = ScanRecord(
        scan_id=scan.scan_id,
        timestamp=scan.timestamp,
        subnet=scan.subnet,
        scan_mode=scan.scan_mode,
        metadata_json=scan.metadata,
    )
    session.add(scan_record)
    session.commit()
    session.refresh(scan_record)

    scan_host_index: dict[str, ScanHostRecord] = {}
    port_index: dict[tuple[str, int, str], PortRecord] = {}

    for artifact in scan.artifacts:
        session.add(
            ArtifactRecord(
                scan_id=scan.scan_id,
                kind=artifact.kind,
                path=artifact.path,
                stage=artifact.stage,
                host_ip=str(artifact.host_ip) if artifact.host_ip is not None else None,
            )
        )

    for host in scan.hosts:
        scan_host_record = _persist_scan_host(session, scan.scan_id, host)
        scan_host_index[str(host.ip)] = scan_host_record
        for port in host.ports:
            port_record = _persist_port(session, scan_host_record.id, port)
            port_index[(str(host.ip), port.port, port.protocol)] = port_record

    session.commit()

    for finding in scan.findings:
        scan_host_record = (
            scan_host_index.get(str(finding.ip)) if finding.ip is not None else None
        )
        port_record = None
        if (
            finding.ip is not None
            and finding.port is not None
            and finding.protocol is not None
        ):
            port_record = port_index.get(
                (str(finding.ip), finding.port, finding.protocol)
            )
        upsert_finding(
            session,
            scan_id=scan.scan_id,
            finding=finding,
            scan_host_record=scan_host_record,
            port_record=port_record,
        )

    upsert_hosts_for_scan(session, scan_record, scan)

    _enqueue_enrichment_jobs(session, scan.scan_id, port_index.values())
    session.commit()
    return scan_record


def upsert_finding(
    session: Session,
    *,
    scan_id,
    finding: Finding,
    scan_host_record: ScanHostRecord | None,
    port_record: PortRecord | None,
    confidence: str | None = None,
    extra_source: str | None = None,
    references: Iterable[str] | None = None,
    evidence_suffix: str | None = None,
) -> FindingRecord:
    dedupe_key = finding_dedupe_key(
        ip=str(finding.ip) if finding.ip is not None else None,
        port=finding.port,
        protocol=finding.protocol,
        cve_id=finding.cve_id,
        title=finding.title,
    )
    existing = session.exec(
        select(FindingRecord).where(
            FindingRecord.scan_id == scan_id,
            FindingRecord.dedupe_key == dedupe_key,
        )
    ).first()
    now = datetime.now(timezone.utc)
    source_labels = [
        value
        for value in [finding.source, finding.source_script, extra_source]
        if value is not None
    ]
    merged_references = sorted(set((references or [])).union(finding.references))
    chosen_confidence = confidence or initial_confidence_for_finding(finding)

    if existing is None:
        record = FindingRecord(
            scan_id=scan_id,
            scan_host_id=scan_host_record.id if scan_host_record is not None else None,
            port_id=port_record.id if port_record is not None else None,
            ip=str(finding.ip) if finding.ip is not None else None,
            port=finding.port,
            protocol=finding.protocol,
            service=finding.service,
            source=finding.source,
            source_script=finding.source_script,
            cve_id=finding.cve_id,
            cvss_score=finding.cvss_score,
            severity=finding.severity,
            confidence=chosen_confidence,
            title=finding.title,
            description=finding.description,
            recommendation=finding.recommendation,
            evidence=_merge_evidence(finding.evidence, evidence_suffix),
            references_json=merged_references,
            source_labels_json=sorted(set(source_labels)),
            dedupe_key=dedupe_key,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.flush()
        refresh_risk_snapshot(session, record)
        return record

    existing.cvss_score = _prefer_float(existing.cvss_score, finding.cvss_score)
    existing.severity = _max_severity(existing.severity, finding.severity)
    existing.confidence = _max_confidence(existing.confidence, chosen_confidence)
    existing.references_json = sorted(
        set(existing.references_json).union(merged_references)
    )
    existing.source_labels_json = sorted(
        set(existing.source_labels_json).union(source_labels)
    )
    existing.evidence = _merge_evidence(existing.evidence, evidence_suffix)
    existing.updated_at = now
    if existing.source is None:
        existing.source = finding.source
    if existing.source_script is None:
        existing.source_script = finding.source_script
    refresh_risk_snapshot(session, existing)
    return existing


def finding_dedupe_key(
    *,
    ip: str | None,
    port: int | None,
    protocol: str | None,
    cve_id: str | None,
    title: str,
) -> str:
    suffix = cve_id or title.strip().lower()
    return f"{ip or 'global'}|{protocol or 'na'}|{port or 0}|{suffix}"


def initial_confidence_for_finding(finding: Finding) -> str:
    if finding.cve_id:
        return "probable"
    return "tentative"


def _persist_scan_host(session: Session, scan_id, host: Host) -> ScanHostRecord:
    record = ScanHostRecord(
        scan_id=scan_id,
        ip=str(host.ip),
        mac=host.mac,
        hostname=host.hostname,
        vendor=host.vendor,
    )
    session.add(record)
    session.flush()
    return record


def _persist_port(session: Session, scan_host_id: int | None, port: Port) -> PortRecord:
    if scan_host_id is None:
        raise ValueError("scan_host_id is required to persist a port")

    port_record = PortRecord(
        scan_host_id=scan_host_id,
        port=port.port,
        protocol=port.protocol,
        state=port.state,
    )
    session.add(port_record)
    session.flush()
    session.add(
        ServiceRecord(
            port_id=port_record.id,
            name=port.service,
            version=port.version,
        )
    )
    for cpe in sorted(set(port.cpes)):
        session.add(CPERecord(port_id=port_record.id, cpe=cpe))
    session.flush()
    return port_record


def _enqueue_enrichment_jobs(
    session: Session,
    scan_id,
    port_records: Iterable[PortRecord],
) -> None:
    seen: set[tuple[str, int | None, str]] = set()
    for port_record in port_records:
        cpes = session.exec(
            select(CPERecord).where(CPERecord.port_id == port_record.id)
        ).all()
        for cpe_record in cpes:
            key = ("nvd_cpe", port_record.id, cpe_record.cpe)
            if key in seen:
                continue
            seen.add(key)
            session.add(
                EnrichmentJobRecord(
                    scan_id=scan_id,
                    port_id=port_record.id,
                    job_type="nvd_cpe",
                    target_value=cpe_record.cpe,
                )
            )

    findings = session.exec(
        select(FindingRecord).where(
            FindingRecord.scan_id == scan_id,
            FindingRecord.cve_id.is_not(None),
        )
    ).all()
    for finding in findings:
        if finding.cve_id is None:
            continue
        key = ("nvd_cve", finding.id, finding.cve_id)
        if key in seen:
            continue
        seen.add(key)
        session.add(
            EnrichmentJobRecord(
                scan_id=scan_id,
                finding_id=finding.id,
                job_type="nvd_cve",
                target_value=finding.cve_id,
            )
        )
        for job_type in ("kev_cve", "epss_cve"):
            key = (job_type, finding.id, finding.cve_id)
            if key in seen:
                continue
            seen.add(key)
            session.add(
                EnrichmentJobRecord(
                    scan_id=scan_id,
                    finding_id=finding.id,
                    job_type=job_type,
                    target_value=finding.cve_id,
                )
            )


def _merge_evidence(base: str, evidence_suffix: str | None) -> str:
    if not evidence_suffix or evidence_suffix in base:
        return base
    return f"{base} | {evidence_suffix}"


def _prefer_float(current: float | None, candidate: float | None) -> float | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return max(current, candidate)


def _max_severity(current: str, candidate: str) -> str:
    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return current if order.get(current, 0) >= order.get(candidate, 0) else candidate


def _max_confidence(current: str, candidate: str) -> str:
    order = {"tentative": 1, "probable": 2, "confirmed": 3}
    return current if order.get(current, 0) >= order.get(candidate, 0) else candidate
