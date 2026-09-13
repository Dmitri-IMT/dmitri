from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from api.models.persistence import EpssRecord, KevRecord
from api.services.ai.schemas import AIFindingContext, ScanAIContext
from api.services.read import get_scan_detail, get_scan_risk_summary

MAX_DESCRIPTION_LENGTH = 4000
MAX_RECOMMENDATION_LENGTH = 2000
MAX_EVIDENCE_LENGTH = 4000
MAX_REFERENCES = 10
MAX_REFERENCE_LENGTH = 2000
MAX_AI_FINDINGS = 15


class ScanAINotReadyError(ValueError):
    pass


def build_scan_ai_context(
    session: Session,
    scan_id: UUID,
    *,
    org_id: UUID,
    max_findings: int = 10,
) -> ScanAIContext | None:
    if not 1 <= max_findings <= MAX_AI_FINDINGS:
        raise ValueError(
            f"max_findings must be between 1 and {MAX_AI_FINDINGS}"
        )

    scan = get_scan_detail(session, scan_id, org_id=org_id)
    if scan is None:
        return None
    if scan.status != "completed":
        raise ScanAINotReadyError("scan must be completed before AI analysis")

    risk = get_scan_risk_summary(
        session,
        scan_id,
        org_id=org_id,
        top_limit=max_findings,
    )
    if risk is None:
        return None

    cve_ids = {
        finding.cve_id.upper()
        for finding in risk.top_findings
        if finding.cve_id is not None
    }
    epss_by_cve = _epss_by_cve(session, cve_ids)
    kev_by_cve = _kev_by_cve(session, cve_ids)

    findings = []
    for finding in risk.top_findings:
        cve_id = finding.cve_id.upper() if finding.cve_id is not None else None
        epss = epss_by_cve.get(cve_id) if cve_id is not None else None
        kev = kev_by_cve.get(cve_id) if cve_id is not None else None
        findings.append(
            AIFindingContext(
                finding_id=finding.finding_id,
                host_id=finding.host_id,
                host_ip=finding.host_ip,
                port=finding.port,
                protocol=finding.protocol,
                service=finding.service,
                cve_id=finding.cve_id,
                cvss_score=finding.cvss_score,
                severity=finding.severity,
                confidence=finding.confidence,
                risk_score=finding.risk_score,
                exploitability=finding.exploitability,
                epss_score=epss.epss_score if epss is not None else None,
                epss_percentile=epss.percentile if epss is not None else None,
                is_kev=kev is not None,
                known_ransomware=kev.known_ransomware if kev is not None else False,
                title=_clip(finding.title, 500),
                description=_clip(finding.description, MAX_DESCRIPTION_LENGTH),
                recommendation=_clip(
                    finding.recommendation, MAX_RECOMMENDATION_LENGTH
                ),
                evidence=_clip(finding.evidence, MAX_EVIDENCE_LENGTH),
                references=[
                    _clip(reference, MAX_REFERENCE_LENGTH)
                    for reference in finding.references[:MAX_REFERENCES]
                ],
            )
        )

    return ScanAIContext(
        scan_id=scan.scan_id,
        timestamp=scan.timestamp,
        subnet=scan.subnet,
        scan_mode=scan.scan_mode,
        duration_seconds=scan.duration,
        host_count=scan.host_count,
        total_findings=risk.total_findings,
        scored_findings=risk.scored_findings,
        confirmed_findings=risk.confirmed_findings,
        kev_findings=risk.kev_findings,
        average_risk_score=risk.average_risk_score,
        max_risk_score=risk.max_risk_score,
        severity=risk.severity,
        top_findings=findings,
    )


def _epss_by_cve(session: Session, cve_ids: set[str]) -> dict[str, EpssRecord]:
    if not cve_ids:
        return {}
    rows = session.exec(
        select(EpssRecord).where(EpssRecord.cve_id.in_(cve_ids))
    ).all()
    return {row.cve_id.upper(): row for row in rows}


def _kev_by_cve(session: Session, cve_ids: set[str]) -> dict[str, KevRecord]:
    if not cve_ids:
        return {}
    rows = session.exec(
        select(KevRecord).where(KevRecord.cve_id.in_(cve_ids))
    ).all()
    return {row.cve_id.upper(): row for row in rows}


def _clip(value: str, max_length: int) -> str:
    return value[:max_length]
