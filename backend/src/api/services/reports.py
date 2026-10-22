from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from api.models.persistence import EnrichmentJobRecord, NvdCacheRecord
from api.schemas.ai import AILanguage, ScanAIAnalysisCompleted
from api.schemas.read import ScanDetailResponse, ScanRiskSummaryResponse
from api.schemas.reports import (
    ExplainedReportSections,
    ReportAction,
    ReportFinding,
    ReportKind,
    ScanReportResponse,
    TechnicalReportSections,
)
from api.services.ai.jobs import get_scan_ai_analysis
from api.services.nvd import parse_nvd_matches
from api.services.read import get_scan_detail, get_scan_risk_summary
from api.services.report_education import (
    build_report_education,
    industrial_protocol_summary,
    report_data_boundary,
)


class ReportNotReadyError(ValueError):
    pass


def build_scan_report(
    session: Session,
    scan_id: UUID,
    *,
    org_id: UUID,
    kind: ReportKind,
    ai_enabled: bool,
    language: AILanguage = "en",
    now: datetime | None = None,
) -> ScanReportResponse | None:
    detail = get_scan_detail(session, scan_id, org_id=org_id)
    if detail is None:
        return None
    if detail.status != "completed":
        raise ReportNotReadyError("scan must be completed before a report is generated")
    risk = get_scan_risk_summary(session, scan_id, org_id=org_id)
    if risk is None:
        raise ReportNotReadyError("risk summary is not available")
    analysis = get_scan_ai_analysis(
        session, scan_id, org_id=org_id, ai_enabled=ai_enabled, language=language,
    )
    completed = analysis if isinstance(analysis, ScanAIAnalysisCompleted) else None
    sections: ExplainedReportSections | TechnicalReportSections
    if kind == "explained":
        advisories, enrichment = _educational_evidence(session, detail)
        education = build_report_education(
            detail, language, advisories=advisories, enrichment=enrichment,
            analysis=completed.analysis if completed else None,
        )
        sections = ExplainedReportSections(
            **education,
            scan_timestamp=detail.timestamp,
            scope=detail.subnet,
            scan_mode=detail.scan_mode,
            ai_explanation_available=completed is not None,
            overview=(
                completed.analysis.plain_language_summary if completed else
                _fallback_overview(language, len(education["devices"]),
                                   len(education["appendix"]))
            ),
            actions=_report_actions(risk, completed, education["appendix"], language),
            method=_method_text(language),
            limitations=(
                list(completed.analysis.uncertainties) if completed else
                [_fallback_limitation(language)]
            ) + _method_limitations(language, detail.assessment_status),
        )
    else:
        industrial_protocols = industrial_protocol_summary(detail.hosts)
        safe_detail = report_data_boundary(detail)
        sections = TechnicalReportSections(
            scan_timestamp=detail.timestamp, scope=detail.subnet,
            scan_mode=detail.scan_mode, scan=safe_detail,
            industrial_protocols=industrial_protocols, risk_summary=risk,
            ai_analysis=completed,
        )
    extension = "pdf" if kind == "explained" else "json"
    return ScanReportResponse(
        scan_id=scan_id, kind=kind, language=language,
        generated_at=now or datetime.now(timezone.utc),
        filename=f"dmitri-scan-{scan_id}-{kind}.{extension}",
        content_type="application/pdf" if kind == "explained" else "application/json",
        sections=sections,
    )


def _educational_evidence(
    session: Session, detail: ScanDetailResponse
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Read already stored advisory data; exporting a report never fetches it."""
    codes = {finding.cve_id for finding in detail.findings if finding.cve_id}
    advisories: dict[str, dict[str, Any]] = {}
    if codes:
        cached = session.exec(
            select(NvdCacheRecord).where(
                NvdCacheRecord.query_kind == "cve",
                NvdCacheRecord.query_value.in_(codes),
            )
        ).all()
        for record in cached:
            for advisory in parse_nvd_matches(record.response_json):
                if advisory["cve_id"] in codes:
                    advisories[advisory["cve_id"]] = {
                        **advisory, "fetched_at": record.fetched_at.isoformat()
                    }
    statuses = dict(session.exec(
        select(EnrichmentJobRecord.status, func.count(EnrichmentJobRecord.id))
        .where(EnrichmentJobRecord.scan_id == detail.scan_id)
        .group_by(EnrichmentJobRecord.status)
    ).all())
    return advisories, {
        "pending": statuses.get("pending", 0) + statuses.get("running", 0),
        "failed": statuses.get("failed", 0),
    }


def _report_actions(
    risk: ScanRiskSummaryResponse,
    completed: ScanAIAnalysisCompleted | None,
    appendix: list[ReportFinding],
    language: AILanguage,
) -> list[ReportAction]:
    if completed and completed.analysis.priority_actions:
        return [action.model_dump(mode="json")
                for action in completed.analysis.priority_actions]
    records = {item["finding_id"]: item for item in appendix}
    actions = []
    for finding in risk.top_findings[:3]:
        record = records[str(finding.finding_id)]
        actions.append(ReportAction(
            priority={"critical": "immediate", "high": "high",
                      "medium": "medium", "low": "low"}[record["severity"]],
            title=finding.title, description=record["recommendation"],
            related_finding_ids=[record["finding_id"]],
        ))
    return actions or [ReportAction(
        priority="medium", title=_fallback_action(language),
        description=_fallback_action(language), related_finding_ids=[],
    )]


def _method_text(language: AILanguage) -> str:
    return {
        "en": (
            "The scan checks devices and services that respond on the network, "
            "using the selected mode. It records observations and known security "
            "issues; it does not test every possible weakness."
        ),
        "pt-BR": (
            "A varredura verifica os equipamentos e serviços que respondem na "
            "rede, conforme o modo escolhido. Ela registra observações e problemas "
            "de segurança conhecidos, mas não testa todas as falhas possíveis."
        ),
        "ru": (
            "Сканирование проверяет устройства и службы, отвечающие в сети, "
            "в выбранном режиме. Оно фиксирует наблюдения и известные проблемы "
            "безопасности, но не проверяет все возможные уязвимости."
        ),
    }[language]


def _method_limitations(language: AILanguage, assessment_status: str) -> list[str]:
    common = {
        "en": [
            "A scan is a snapshot of what responded at that time; it cannot "
            "prove that a device was never compromised.",
            "Finding records are observations, not a count of unique "
            "vulnerabilities. CVSS describes a technical issue and is not "
            "a measure of the network's overall risk.",
        ],
        "pt-BR": [
            "A varredura mostra o que respondeu naquele momento; ela não "
            "comprova que um equipamento nunca foi invadido.",
            "Achados são registros de observações, não uma contagem de "
            "vulnerabilidades únicas. O CVSS descreve uma falha técnica "
            "e não mede o risco geral da rede.",
        ],
        "ru": [
            "Сканирование отражает ответы устройств в конкретный момент "
            "и не доказывает, что устройство никогда не было взломано.",
            "Записи о находках являются наблюдениями, а не подсчетом "
            "уникальных уязвимостей. CVSS описывает техническую проблему, "
            "но не общий риск сети.",
        ],
    }[language]
    if assessment_status == "unavailable":
        common.append({
            "en": "Device exposure assessment was unavailable for this scan.",
            "pt-BR": (
                "A avaliação de exposição dos equipamentos não estava "
                "disponível nesta varredura."
            ),
            "ru": "Оценка открытых служб устройств для этого сканирования недоступна.",
        }[language])
    return common


def _fallback_overview(language: AILanguage, hosts: int, findings: int) -> str:
    return {
        "en": (
            f"The scan observed {hosts} devices and returned "
            f"{findings} finding records."
        ),
        "pt-BR": (
            f"A varredura observou {hosts} equipamentos e retornou "
            f"{findings} registros de achados."
        ),
        "ru": (
            f"Сканирование обнаружило устройств: {hosts}; "
            f"записей о находках: {findings}."
        ),
    }[language]


def _fallback_action(language: AILanguage) -> str:
    return {
        "en": "Ask an IT professional to review the findings.",
        "pt-BR": "Peça a um profissional de TI para revisar os achados.",
        "ru": "Попросите специалиста по ИТ проверить находки.",
    }[language]


def _fallback_limitation(language: AILanguage) -> str:
    return {
        "en": "An AI explanation was not available for this scan.",
        "pt-BR": "A explicação da IA não está disponível para esta varredura.",
        "ru": "Объяснение ИИ для этого сканирования недоступно.",
    }[language]
