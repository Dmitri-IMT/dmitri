from __future__ import annotations

from uuid import UUID

from api.schemas.ai import AIChatResponse, ProviderAIChatResponse
from api.schemas.read import ScanDetailResponse, ScanRiskSummaryResponse


def build_chat_context(
    detail: ScanDetailResponse,
    risk: ScanRiskSummaryResponse,
    analysis: object | None,
) -> dict[str, object]:
    """Build a bounded, read-only context for one scan question."""
    completed_analysis = getattr(analysis, "analysis", None)
    analysis_context = None
    if completed_analysis is not None:
        analysis_context = {
            "plain_language_summary": _clip(
                completed_analysis.plain_language_summary, 1200
            ),
            "overall_assessment": _clip(completed_analysis.overall_assessment, 1200),
            "priority_actions": [
                {
                    "priority": action.priority,
                    "title": _clip(action.title, 180),
                    "description": _clip(action.description, 400),
                }
                for action in completed_analysis.priority_actions[:5]
            ],
            "uncertainties": [
                _clip(item, 400) for item in completed_analysis.uncertainties[:5]
            ],
        }

    return {
        "scan": {
            "scan_id": str(detail.scan_id),
            "timestamp": detail.timestamp.isoformat(),
            "subnet": detail.subnet,
            "scan_mode": detail.scan_mode,
            "status": detail.status,
            "host_count": detail.host_count,
            "finding_count": detail.finding_count,
        },
        "risk_summary": {
            "total_findings": risk.total_findings,
            "scored_findings": risk.scored_findings,
            "confirmed_findings": risk.confirmed_findings,
            "kev_findings": risk.kev_findings,
            "average_risk_score": risk.average_risk_score,
            "max_risk_score": risk.max_risk_score,
            "severity": risk.severity.model_dump(mode="json"),
        },
        "top_findings": [
            {
                "finding_ref": f"finding_{index}",
                "finding_id": str(finding.finding_id),
                "title": _clip(finding.title, 180),
                "description": _clip(finding.description, 500),
                "recommendation": _clip(finding.recommendation, 500),
                "severity": finding.severity,
                "cve_id": finding.cve_id,
                "cvss_score": finding.cvss_score,
                "risk_score": finding.risk_score,
                "host_ip": str(finding.host_ip) if finding.host_ip else None,
                "host_hostname": finding.host_hostname,
                "port": finding.port,
                "service": finding.service,
            }
            for index, finding in enumerate(risk.top_findings[:5], start=1)
        ],
        "existing_ai_analysis": analysis_context,
    }


def _clip(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"


def materialize_chat_response(
    response: ProviderAIChatResponse,
    finding_ids_by_ref: dict[str, UUID],
) -> AIChatResponse:
    unknown = set(response.referenced_finding_refs) - set(finding_ids_by_ref)
    if unknown:
        raise ValueError("chat response contains an unknown finding reference")
    return AIChatResponse(
        answer=response.answer,
        uncertainties=response.uncertainties,
        referenced_finding_ids=[
            finding_ids_by_ref[reference]
            for reference in response.referenced_finding_refs
        ],
    )


def finding_reference_map(risk: ScanRiskSummaryResponse) -> dict[str, UUID]:
    return {
        f"finding_{index}": finding.finding_id
        for index, finding in enumerate(risk.top_findings, start=1)
    }
