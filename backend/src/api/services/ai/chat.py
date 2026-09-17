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
        "risk_summary": risk.model_dump(mode="json"),
        "top_findings": [
            {
                "finding_ref": f"finding_{index}",
                "finding_id": str(finding.finding_id),
                "title": finding.title,
                "description": finding.description,
                "recommendation": finding.recommendation,
                "severity": finding.severity,
                "cve_id": finding.cve_id,
                "cvss_score": finding.cvss_score,
                "risk_score": finding.risk_score,
                "host_ip": str(finding.host_ip) if finding.host_ip else None,
                "host_hostname": finding.host_hostname,
                "port": finding.port,
                "service": finding.service,
            }
            for index, finding in enumerate(risk.top_findings, start=1)
        ],
        "existing_ai_analysis": (
            analysis.model_dump(mode="json") if analysis is not None else None
        ),
    }


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
