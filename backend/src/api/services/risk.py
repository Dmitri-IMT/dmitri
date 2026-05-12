from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from api.models.persistence import (
    EpssRecord,
    FindingRecord,
    KevRecord,
    RiskSnapshotRecord,
)

SEVERITY_WEIGHTS = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}

CONFIDENCE_WEIGHTS = {
    "tentative": 0.5,
    "probable": 0.75,
    "confirmed": 1.0,
}


def refresh_risk_snapshot(
    session: Session,
    finding: FindingRecord,
) -> RiskSnapshotRecord:
    if finding.id is None:
        raise ValueError("finding must be persisted before risk scoring")

    kev_record = (
        session.get(KevRecord, finding.cve_id.upper()) if finding.cve_id else None
    )
    epss_record = (
        session.get(EpssRecord, finding.cve_id.upper()) if finding.cve_id else None
    )

    severity_weight = SEVERITY_WEIGHTS.get(finding.severity, 0.5)
    confidence_weight = CONFIDENCE_WEIGHTS.get(finding.confidence, 0.5)
    epss_score = epss_record.epss_score if epss_record is not None else 0.0
    kev_boost = 0.3 if kev_record is not None else 0.0
    ransomware_boost = (
        0.1 if kev_record is not None and kev_record.known_ransomware else 0.0
    )
    exposed_service_boost = 0.05 if finding.port is not None else 0.0

    exploitability = min(
        1.0,
        round((epss_score * 0.7) + kev_boost + ransomware_boost, 4),
    )
    risk_score = min(
        100.0,
        round(
            (
                severity_weight * 45.0
                + exploitability * 35.0
                + confidence_weight * 15.0
                + exposed_service_boost * 100.0
            ),
            2,
        ),
    )

    rationale_parts = [
        f"severity={finding.severity}",
        f"confidence={finding.confidence}",
    ]
    if epss_record is not None:
        rationale_parts.append(f"epss={epss_record.epss_score:.3f}")
    if kev_record is not None:
        rationale_parts.append("kev=yes")
        if kev_record.known_ransomware:
            rationale_parts.append("known_ransomware=yes")
    else:
        rationale_parts.append("kev=no")

    existing = session.exec(
        select(RiskSnapshotRecord).where(RiskSnapshotRecord.finding_id == finding.id)
    ).first()
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = RiskSnapshotRecord(
            finding_id=finding.id,
            confidence=finding.confidence,
            exploitability=exploitability,
            risk_score=risk_score,
            rationale=", ".join(rationale_parts),
            created_at=now,
            updated_at=now,
        )
        session.add(existing)
        session.flush()
        return existing

    existing.confidence = finding.confidence
    existing.exploitability = exploitability
    existing.risk_score = risk_score
    existing.rationale = ", ".join(rationale_parts)
    existing.updated_at = now
    session.add(existing)
    session.flush()
    return existing
