from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class RiskParts:
    severity: float
    likelihood: float
    confidence: float
    reachable: float

    @property
    def total(self) -> float:
        return min(
            100.0,
            round(
                self.severity + self.likelihood + self.confidence + self.reachable,
                2,
            ),
        )


def risk_parts(
    severity: str, confidence: str | None, port: int | None, exploitability: float
) -> RiskParts:
    return RiskParts(
        severity=SEVERITY_WEIGHTS.get(severity, 0.5) * 45.0,
        likelihood=exploitability * 35.0,
        confidence=CONFIDENCE_WEIGHTS.get(confidence or "", 0.5) * 15.0,
        reachable=5.0 if port is not None else 0.0,
    )


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

    epss_score = epss_record.epss_score if epss_record is not None else 0.0
    kev_boost = 0.3 if kev_record is not None else 0.0
    ransomware_boost = (
        0.1 if kev_record is not None and kev_record.known_ransomware else 0.0
    )
    exploitability = min(
        1.0,
        round((epss_score * 0.7) + kev_boost + ransomware_boost, 4),
    )
    risk_score = risk_parts(
        finding.severity, finding.confidence, finding.port, exploitability
    ).total

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
