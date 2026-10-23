from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from api.schemas.ai import MachineExplanation, ScanExplanation
from api.services.ai.chat import (
    AIChatContextBundle,
    build_host_chat_bundle,
    build_scan_chat_bundle,
    context_findings,
    scrub_secrets,
)
from api.services.ai.context import (
    describe_observed_products,
    reference_names,
    replace_ai_references,
)
from api.services.ai.openai_responses import AIProviderError
from api.services.ai.writing import (
    machine_explanation_violations,
    scan_explanation_violations,
)
from api.services.read import (
    get_host_detail,
    get_scan_detail,
    get_scan_risk_summary,
    list_findings,
)


def explanation_context(
    session: Session, scope: str, context_id: UUID, org_id: UUID, language: str
) -> tuple[AIChatContextBundle, UUID, list[str]] | None:
    leads: list[str] = []
    if scope == "scan":
        detail = get_scan_detail(session, context_id, org_id=org_id)
        if detail is None or detail.status != "completed":
            return None
        risk = get_scan_risk_summary(session, context_id, org_id=org_id)
        if risk is None:
            return None
        bundle = build_scan_chat_bundle(detail, risk)
        for severity in ("critical", "high", "medium", "low"):
            count = getattr(risk.severity, severity)
            if count:
                labels = {
                    "en": {
                        'critical': 'critical problems',
                        'high': 'high-level problems',
                        'medium': 'medium-level problems',
                        'low': 'low-level problems',
                    },
                    "pt-BR": {
                        'critical': 'problemas críticos',
                        'high': 'problemas de nível alto',
                        'medium': 'problemas de nível médio',
                        'low': 'problemas de nível baixo',
                    },
                    "ru": {
                        'critical': 'критических проблем',
                        'high': 'проблем высокого уровня',
                        'medium': 'проблем среднего уровня',
                        'low': 'проблем низкого уровня',
                    },
                }
                leads.append(f"{count} {labels[language][severity]}.")
        labels = {
            "en": (
                'problems used in real attacks',
                'machines with no known problems',
                'checks did not finish',
            ),
            "pt-BR": (
                'problemas usados em ataques reais',
                'máquinas sem problemas conhecidos',
                'verificações não concluídas',
            ),
            "ru": (
                'проблем используются в реальных атаках',
                'машин без известных проблем',
                'проверок не завершено',
            ),
        }[language]
        affected = {finding.host_id for finding in detail.findings}
        clean = sum(host.host_id not in affected for host in detail.hosts)
        for count, label in zip(
            (risk.kev_findings, clean, bundle.provider_context.incomplete_check_count),
            labels,
            strict=True,
        ):
            if count:
                leads.append(f"{count} {label}.")
        scan_id = context_id
    else:
        host = get_host_detail(session, context_id, org_id=org_id)
        if host is None or not host.scan_history:
            return None
        scan_id = host.scan_history[0].scan_id
        findings = list_findings(
            session, org_id=org_id, host_id=context_id, scan_id=scan_id, per_page=100
        )
        bundle = build_host_chat_bundle(host, findings.data, findings.evidence_summary)
        bundle.provider_context.vulnerability_count = findings.total
    finding_contexts = context_findings(bundle.provider_context)
    describe_observed_products(session, finding_contexts, bundle.finding_ids_by_ref)
    for finding in finding_contexts:
        for field in ("product", "version", "service"):
            text = getattr(finding, field)
            if text is not None:
                setattr(finding, field, scrub_secrets(text))
    return bundle, scan_id, leads


def materialize_explanation(
    value: ScanExplanation | MachineExplanation,
    bundle: AIChatContextBundle,
    allowed_leads: list[str],
) -> ScanExplanation | MachineExplanation:
    if isinstance(value, ScanExplanation):
        violations = scan_explanation_violations(value)
        if any(point.lead not in allowed_leads for point in value.meanings):
            violations.append("unverified_count")
    else:
        violations = machine_explanation_violations(value)
    references = set(reference_names(value.model_dump_json()))
    if not references <= bundle.display_values_by_ref.keys():
        violations.append("unknown_reference")
    if (
        isinstance(value, ScanExplanation)
        and len({p.lead for p in value.meanings}) != len(value.meanings)
    ):
        violations.append("duplicate_meaning")
    if violations:
        raise AIProviderError("invalid_provider_response", retryable=False)

    def clean(item: Any) -> Any:
        if isinstance(item, str):
            return replace_ai_references(
                scrub_secrets(item), bundle.display_values_by_ref
            )
        if isinstance(item, list):
            return [clean(part) for part in item]
        if isinstance(item, dict):
            return {key: clean(part) for key, part in item.items()}
        return item

    return type(value).model_validate(clean(value.model_dump()))
