from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlmodel import Session, select

from api.dependencies.agent_auth import AgentIdentity
from api.models.command import Command
from api.models.persistence import (
    CPERecord,
    EnrichmentJobRecord,
    ExposureRecord,
    FindingRecord,
    ModbusUnitRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.schemas.scan import (
    TERMINATED_BY_USER_CANCEL,
    ExposurePayload,
    FindingEvidenceObservationPayload,
    FindingPayload,
    HostPayload,
    PortPayload,
    ScanIngestRequest,
)
from api.services.activity import append_scan_activity
from api.services.ai.jobs import enqueue_auto_scan_analysis
from api.services.command_lifecycle import accepts_late_ingest, is_terminal
from api.services.commands import command_for_scan, transition_command
from api.services.hosts import upsert_hosts_for_scan
from api.services.industrial import persist_industrial_services
from api.services.inventory import reconcile_scan_inventory
from api.services.risk import refresh_risk_snapshot
from api.services.scan_evidence import reduce_finding_evidence


class ScanOwnershipError(Exception):
    pass


class ScanClosedError(Exception):
    pass


def ingest_scan(
    session: Session,
    scan: ScanIngestRequest,
    *,
    identity: AgentIdentity,
    now: datetime,
) -> ScanRecord:
    existing = session.get(ScanRecord, scan.scan_id)

    if existing is None:
        return persist_scan(
            session,
            scan,
            org_id=identity.org_id,
            agent_id=identity.agent_id,
            command=None,
            now=now,
            existing=None,
        )

    if existing.status == "completed":
        if existing.agent_id != identity.agent_id or existing.org_id != identity.org_id:
            raise ScanOwnershipError
        return existing

    command = command_for_scan(session, scan.scan_id)
    if (
        command is None
        or command.agent_id != identity.agent_id
        or command.org_id != identity.org_id
    ):
        raise ScanOwnershipError
    return persist_scan(
        session,
        scan,
        org_id=identity.org_id,
        agent_id=identity.agent_id,
        command=command,
        now=now,
        existing=existing,
    )


def persist_scan(
    session: Session,
    scan: ScanIngestRequest,
    *,
    org_id: UUID,
    agent_id: UUID,
    command: Command | None,
    now: datetime,
    existing: ScanRecord | None,
) -> ScanRecord:
    command_status = (
        None
        if command is None
        else session.exec(
            select(Command.status).where(Command.id == command.id).with_for_update()
        ).one()
    )
    if (
        command_status is not None
        and is_terminal(command_status)
        and not accepts_late_ingest(command_status)
    ):
        raise ScanClosedError
    if existing is None:
        scan_record = ScanRecord(
            scan_id=scan.scan_id,
            org_id=org_id,
            agent_id=agent_id,
            timestamp=scan.timestamp,
            subnet=scan.subnet,
            scan_mode=scan.scan_mode,
            metadata_json=scan.metadata,
            coverage_json=[unit.model_dump(mode="json") for unit in scan.coverage],
            finding_evidence_policy_version=scan.finding_evidence_policy_version,
            finding_observations_json=(
                _merge_observation_json([], scan.finding_observations)
                if scan.finding_evidence_policy_version is not None
                else None
            ),
            finding_observations_truncated=scan.finding_observations_truncated,
            assessment_policy_version=scan.assessment_policy_version,
            status="completed",
        )
        session.add(scan_record)
    else:
        scan_record = existing
        if (
            scan_record.agent_id is not None
            and scan_record.agent_id != agent_id
        ):
            raise ScanOwnershipError
        scan_record.timestamp = scan.timestamp
        scan_record.subnet = scan.subnet
        scan_record.scan_mode = scan.scan_mode
        scan_record.metadata_json = scan.metadata
        scan_record.coverage_json = [
            unit.model_dump(mode="json") for unit in scan.coverage
        ]
        scan_record.finding_evidence_policy_version = (
            scan.finding_evidence_policy_version
            or scan_record.finding_evidence_policy_version
        )
        full_scan_observations = _all_observation_json(
            scan_record.finding_observations_json or [], scan.finding_observations
        )
        merged_scan_observations = full_scan_observations[:512]
        scan_record.finding_observations_json = (
            merged_scan_observations
            if scan_record.finding_evidence_policy_version is not None
            else None
        )
        scan_record.finding_observations_truncated = (
            scan_record.finding_observations_truncated
            or scan.finding_observations_truncated
            or len(full_scan_observations) > 512
        )
        scan_record.status = "completed"
        scan_record.assessment_policy_version = scan.assessment_policy_version
        scan_record.agent_id = agent_id
        session.add(scan_record)
    session.flush()

    scan_host_index: dict[str, ScanHostRecord] = {}
    port_index: dict[tuple[str, int, str], PortRecord] = {}
    modbus_unit_index: dict[tuple[str, int, int], int] = {}

    for host in scan.hosts:
        scan_host_record = _persist_scan_host(session, scan.scan_id, host)
        scan_host_index[str(host.ip)] = scan_host_record
        port_index_host: dict[tuple[int, str], PortRecord] = {}
        for port in host.ports:
            port_record = _persist_port(session, scan_host_record.id, port)
            port_index[(str(host.ip), port.port, port.protocol)] = port_record
            port_index_host[(port.port, port.protocol)] = port_record
        if host.industrial_services:
            unit_rows = persist_industrial_services(
                session,
                scan_host_record.id,
                host.industrial_services,
                port_index=port_index_host,
            )
            for (service_port, unit_id), unit_record in unit_rows.items():
                modbus_unit_index[(str(host.ip), service_port, unit_id)] = (
                    unit_record.id
                )

    for exposure in scan.exposures:
        endpoint = (str(exposure.ip), exposure.port, exposure.protocol)
        scan_host_record = scan_host_index.get(endpoint[0])
        port_record = port_index.get(endpoint)
        if (
            scan_host_record is None
            or port_record is None
            or port_record.state != "open"
        ):
            raise ValueError("exposure must resolve to an open endpoint in this scan")
        _persist_exposure(
            session,
            scan.scan_id,
            scan_host_record,
            port_record,
            exposure,
        )

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
        modbus_unit_id = (
            _resolve_modbus_unit_id(finding, modbus_unit_index, str(finding.ip))
            if finding.ip is not None
            else None
        )
        upsert_finding(
            session,
            scan_id=scan.scan_id,
            finding=finding,
            finding_evidence_policy_version=scan.finding_evidence_policy_version,
            standalone_observations=[
                FindingEvidenceObservationPayload.model_validate(value)
                for value in scan_record.finding_observations_json or []
            ],
            standalone_observations_truncated=(
                scan_record.finding_observations_truncated
            ),
            scan_host_record=scan_host_record,
            port_record=port_record,
            modbus_unit_id=modbus_unit_id,
        )

    if scan.finding_observations or scan.finding_observations_truncated:
        _reassess_scan_findings(session, scan_record)

    upsert_hosts_for_scan(session, scan_record, scan)

    reconcile_scan_inventory(session, scan_record)

    _enqueue_enrichment_jobs(session, scan.scan_id, port_index.values())
    # Enrichment workers call this again when their jobs finish. Calling it
    # here also covers scans that produce no enrichment jobs at all.
    enqueue_auto_scan_analysis(session, scan.scan_id, commit=False)

    _close_scan(
        session,
        scan,
        scan_record,
        command,
        command_status,
        agent_id=agent_id,
        now=now,
    )
    return scan_record


def _close_scan(
    session: Session,
    scan: ScanIngestRequest,
    scan_record: ScanRecord,
    command: Command | None,
    command_status: str | None,
    *,
    agent_id: UUID,
    now: datetime,
) -> None:
    """Record the scan's end and settle its command in one transaction.

    The scan is `completed` because its data arrived; the command follows the
    operator (spec 049, decision 3). The command row stays locked until the
    commit, so an operator cancel cannot land between the read and the write.
    """
    # The Pi's own account of the stop names the activity: a Pi cancelled while
    # offline may still finish normally before it hears the cancel.
    stopped_by_operator = (
        scan.metadata is not None
        and scan.metadata.get("terminated_by") == TERMINATED_BY_USER_CANCEL
    )
    append_scan_activity(
        session,
        org_id=scan_record.org_id,
        scan_id=scan.scan_id,
        kind="scan_cancelled" if stopped_by_operator else "scan_finished",
        scan_mode=scan_record.scan_mode,
        occurred_at=now,
    )
    if (
        command is not None
        and command_status is not None
        and not accepts_late_ingest(command_status)
    ):
        transition_command(
            session,
            agent_id=agent_id,
            command_id=command.id,
            status="cancelled" if stopped_by_operator else "done",
            now=now,
        )
    session.commit()


def upsert_finding(
    session: Session,
    *,
    scan_id: UUID,
    finding: FindingPayload,
    finding_evidence_policy_version: str | None = None,
    standalone_observations: Sequence[FindingEvidenceObservationPayload] = (),
    standalone_observations_truncated: bool = False,
    scan_host_record: ScanHostRecord | None,
    port_record: PortRecord | None,
    confidence: str | None = None,
    extra_source: str | None = None,
    references: Iterable[str] | None = None,
    evidence_suffix: str | None = None,
    modbus_unit_id: int | None = None,
) -> FindingRecord:
    dedupe_key = finding_dedupe_key(
        ip=str(finding.ip) if finding.ip is not None else None,
        port=finding.port,
        protocol=finding.protocol,
        cve_id=finding.cve_id,
        title=finding.title,
        unit_id=finding.unit_id,
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
    existing_policy_version = (
        existing.finding_evidence_policy_version if existing is not None else None
    )
    policy_version = (
        finding_evidence_policy_version or existing_policy_version
    )
    prior_observations = (
        existing.evidence_observations_json or [] if existing is not None else []
    )
    merged_observations = _merge_observation_json(
        prior_observations,
        [*finding.evidence_observations, *standalone_observations],
    )
    evidence_truncated = (
        (existing.evidence_truncated if existing is not None else False)
        or finding.evidence_truncated
        or standalone_observations_truncated
    )
    issue_key = existing.issue_key if existing is not None else None
    issue_key_ambiguous = (
        existing.issue_key_ambiguous if existing is not None else False
    )
    if finding.issue_key is not None:
        if issue_key is None and not issue_key_ambiguous:
            issue_key = finding.issue_key
        elif issue_key != finding.issue_key:
            issue_key = None
            issue_key_ambiguous = True
    allowed_conditions = sorted(
        {
            item.get("condition_key")
            for item in merged_observations
            if isinstance(item.get("condition_key"), str)
        }
    )
    if policy_version is not None:
        assessment = reduce_finding_evidence(
            merged_observations,
            cve_id=finding.cve_id,
            issue_key=issue_key,
            ip=str(finding.ip) if finding.ip is not None else None,
            port=finding.port,
            protocol=finding.protocol,
            unit_id=finding.unit_id,
            policy_version=policy_version,
            evidence_truncated=evidence_truncated,
            issue_key_ambiguous=issue_key_ambiguous,
            allowed_conditions=allowed_conditions,
        )
        merged_observations = [
            item.model_dump(mode="json") for item in assessment.observations
        ]
        evidence_truncated = assessment.evidence_truncated
        chosen_confidence = assessment.confidence
    else:
        chosen_confidence = confidence or initial_confidence_for_finding(finding)
        if issue_key_ambiguous:
            chosen_confidence = "tentative"

    if existing is None:
        record = FindingRecord(
            scan_id=scan_id,
            scan_host_id=scan_host_record.id if scan_host_record is not None else None,
            port_id=port_record.id if port_record is not None else None,
            modbus_unit_id=modbus_unit_id,
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
            finding_evidence_policy_version=policy_version,
            evidence_observations_json=(
                merged_observations if policy_version is not None else None
            ),
            evidence_truncated=evidence_truncated,
            issue_key=issue_key,
            issue_key_ambiguous=issue_key_ambiguous,
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
    existing.confidence = (
        chosen_confidence
        if policy_version is not None or issue_key_ambiguous
        else _max_confidence(existing.confidence, chosen_confidence)
    )
    existing.finding_evidence_policy_version = policy_version
    existing.evidence_observations_json = (
        merged_observations if policy_version is not None else None
    )
    existing.evidence_truncated = evidence_truncated
    existing.issue_key = issue_key
    existing.issue_key_ambiguous = issue_key_ambiguous
    existing.references_json = sorted(
        set(existing.references_json).union(merged_references)
    )
    existing.source_labels_json = sorted(
        set(existing.source_labels_json).union(source_labels)
    )
    existing.evidence = _merge_evidence(
        _merge_evidence(existing.evidence, finding.evidence), evidence_suffix
    )
    if modbus_unit_id is not None:
        existing.modbus_unit_id = modbus_unit_id
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
    unit_id: int | None = None,
) -> str:
    suffix = cve_id or title.strip().lower()
    unit_suffix = str(unit_id) if unit_id is not None else "na"
    return f"{ip or 'global'}|{protocol or 'na'}|{port or 0}|{unit_suffix}|{suffix}"


def initial_confidence_for_finding(finding: FindingPayload) -> str:
    if finding.cve_id:
        return "probable"
    return "tentative"


def _merge_observation_json(
    existing: Sequence[dict[str, Any]] | None,
    incoming: Sequence[FindingEvidenceObservationPayload | dict[str, Any]],
) -> list[dict[str, Any]]:
    return _all_observation_json(existing, incoming)[:512]


def _all_observation_json(
    existing: Sequence[dict[str, Any]] | None,
    incoming: Sequence[FindingEvidenceObservationPayload | dict[str, Any]],
) -> list[dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for item in [*(existing or []), *incoming]:
        value = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        key = json.dumps(value, sort_keys=True, separators=(",", ":"))
        values[key] = value
    return [values[key] for key in sorted(values)]


def _reassess_scan_findings(session: Session, scan_record: ScanRecord) -> None:
    for record in session.exec(
        select(FindingRecord).where(FindingRecord.scan_id == scan_record.scan_id)
    ).all():
        if record.finding_evidence_policy_version is None:
            continue
        observations = _merge_observation_json(
            record.evidence_observations_json or [],
            [
                FindingEvidenceObservationPayload.model_validate(value)
                for value in scan_record.finding_observations_json or []
            ],
        )
        modbus_unit = (
            session.get(ModbusUnitRecord, record.modbus_unit_id)
            if record.modbus_unit_id is not None
            else None
        )
        assessment = reduce_finding_evidence(
            observations,
            cve_id=record.cve_id,
            issue_key=record.issue_key,
            ip=record.ip,
            port=record.port,
            protocol=record.protocol,
            unit_id=modbus_unit.unit_id if modbus_unit is not None else None,
            policy_version=record.finding_evidence_policy_version,
            evidence_truncated=(
                record.evidence_truncated
                or scan_record.finding_observations_truncated
            ),
            issue_key_ambiguous=record.issue_key_ambiguous,
        )
        record.evidence_observations_json = [
            item.model_dump(mode="json") for item in assessment.observations
        ]
        record.evidence_truncated = assessment.evidence_truncated
        record.confidence = assessment.confidence
        session.add(record)
        refresh_risk_snapshot(session, record)


def _persist_scan_host(
    session: Session, scan_id: UUID, host: HostPayload
) -> ScanHostRecord:
    record = ScanHostRecord(
        scan_id=scan_id,
        ip=str(host.ip),
        mac=host.mac,
        hostname=host.hostname,
        vendor=host.vendor,
        operating_system_json=(
            host.operating_system.model_dump(mode="json", exclude_none=True)
            if host.operating_system is not None
            else None
        ),
        machine_type=host.machine_type,
        device_profile_json=(
            host.device_profile.model_dump(mode="json")
            if host.device_profile is not None
            else None
        ),
    )
    session.add(record)
    session.flush()
    return record


def _persist_port(
    session: Session, scan_host_id: int | None, port: PortPayload
) -> PortRecord:
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


def _persist_exposure(
    session: Session,
    scan_id: UUID,
    scan_host_record: ScanHostRecord,
    port_record: PortRecord,
    exposure: ExposurePayload,
) -> ExposureRecord:
    if scan_host_record.id is None or port_record.id is None:
        raise ValueError("exposure endpoints must be persisted before exposure records")
    record = ExposureRecord(
        scan_id=scan_id,
        scan_host_id=scan_host_record.id,
        port_id=port_record.id,
        ip=str(exposure.ip),
        port=exposure.port,
        protocol=exposure.protocol,
        observed_service=exposure.observed_service,
        observed_version=exposure.observed_version,
        role=exposure.role,
        attention=exposure.attention,
        confidence=exposure.confidence,
        reason=exposure.reason,
        evidence_json=[item.model_dump(mode="json") for item in exposure.evidence],
    )
    session.add(record)
    session.flush()
    return record


def _enqueue_enrichment_jobs(
    session: Session,
    scan_id: UUID,
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


def _resolve_modbus_unit_id(
    finding: FindingPayload,
    modbus_unit_index: dict[tuple[str, int, int], int],
    host_ip: str,
) -> int | None:
    """Map a finding to a persisted Modbus unit when the ingest payload names one.

    Findings without ``unit_id`` remain port-attributed until the agent contract
    carries explicit unit attribution on every finding shape.
    """
    if finding.unit_id is None or finding.port is None:
        return None
    return modbus_unit_index.get((host_ip, finding.port, finding.unit_id))
