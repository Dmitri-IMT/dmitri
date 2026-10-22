from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from api.models.persistence import (
    AIScanAnalysisRecord,
    EpssRecord,
    IndustrialServiceRecord,
    KevRecord,
    RiskSnapshotRecord,
)
from api.schemas.ai import (
    AIProviderFindingExplanation,
    AIProviderRecommendedAction,
    ProviderScanAIAnalysis,
)
from api.services.ai.analyzer import split_context
from api.services.ai.context import (
    ScanAINotReadyError,
    build_finding_contexts,
    build_scan_ai_context,
    materialize_scan_ai_analysis,
    summarize_industrial_protocols,
)
from api.services.read import get_scan_detail
from read_factories import seed_read_graph


def test_context_uses_ranked_bounded_enriched_findings(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    other_finding = seeded["other_finding"]
    finding.cve_id = "CVE-2024-10001"
    finding.cvss_score = 9.8
    finding.confidence = "confirmed"
    other_finding.cve_id = "CVE-2024-10002"
    administrative_session.add(finding)
    administrative_session.add(other_finding)
    administrative_session.add(
        EpssRecord(
            cve_id=finding.cve_id,
            epss_score=0.91,
            percentile=0.99,
        )
    )
    administrative_session.add(
        KevRecord(
            cve_id=finding.cve_id,
            known_ransomware=True,
        )
    )
    administrative_session.add(
        RiskSnapshotRecord(
            finding_id=finding.id,
            confidence="confirmed",
            exploitability=0.95,
            risk_score=96,
            rationale="severity=high, confidence=confirmed, kev=yes",
        )
    )
    administrative_session.add(
        RiskSnapshotRecord(
            finding_id=other_finding.id,
            confidence="tentative",
            exploitability=0.1,
            risk_score=20,
            rationale="severity=low, confidence=tentative, kev=no",
        )
    )
    administrative_session.commit()

    context = build_scan_ai_context(
        administrative_session,
        seeded["scan"],
        max_findings=1,
    )

    assert context is not None
    assert context.context_version == "6"
    assert context.host_count == 2
    assert context.total_findings == 2
    assert context.scored_findings == 2
    assert context.confirmed_findings == 1
    assert context.kev_findings == 1
    assert context.average_risk_score == 58
    assert context.max_risk_score == 96
    assert len(context.top_findings) == 1

    top = context.top_findings[0]
    assert top.finding_ref == "finding_1"
    assert top.machine_ref == "machine_1"
    assert top.risk_score == 96
    assert top.cvss_score == 9.8
    assert top.epss_score == 0.91
    assert top.epss_percentile == 0.99
    assert top.is_kev is True
    assert top.known_ransomware is True


@pytest.mark.parametrize(
    ("terminated_by", "stopped_by"),
    [
        ("user_cancel", "operator"),
        ("timeout", "timeout"),
        ("error", "error"),
        (None, None),
    ],
)
def test_context_maps_partial_scan_termination(
    administrative_session,
    terminated_by,
    stopped_by,
):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].metadata_json = {
        "partial_result": True,
        **({"terminated_by": terminated_by} if terminated_by is not None else {}),
    }

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    assert context.context_version == "6"
    assert context.evidence_completeness == "partial"
    assert context.stopped_by == stopped_by


def test_context_marks_complete_scan_as_complete(administrative_session):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].metadata_json = {"partial_result": False}

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    assert context.evidence_completeness == "complete"
    assert context.stopped_by is None


def test_building_v5_context_leaves_saved_analysis_unchanged(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    saved_payload = {"executive_summary": "Saved legacy explanation."}
    saved = AIScanAnalysisRecord(
        scan_id=seeded["scan"].scan_id,
        provider="groq",
        model="legacy-model",
        language="en",
        status="completed",
        analysis_json=saved_payload,
        context_version="4",
        prompt_version="6",
    )
    administrative_session.add(saved)
    administrative_session.commit()

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    administrative_session.refresh(saved)
    assert saved.analysis_json == saved_payload
    assert saved.context_version == "4"
    assert saved.prompt_version == "6"


def test_context_sends_only_public_facts_and_placeholders(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    finding = seeded["finding"]
    finding.cve_id = "CVE-2024-10001"
    administrative_session.add(finding)
    administrative_session.commit()

    context = build_scan_ai_context(administrative_session, seeded["scan"])

    assert context is not None
    payload = context.model_dump_json()
    for value in (
        str(seeded["scan"].scan_id),
        seeded["scan"].subnet,
        str(seeded["host"].id),
        str(finding.finding_id),
        str(finding.ip),
        finding.title,
        finding.description,
        finding.recommendation,
        finding.evidence,
    ):
        assert value not in payload
    assert '"finding_ref":"finding_1"' in payload
    assert '"machine_ref":"machine_1"' in payload


def test_context_includes_only_aggregate_industrial_protocol_facts(
    administrative_session,
):
    seeded = seed_read_graph(administrative_session)
    phase = {"status": "completed", "reason_codes": [], "truncated": False,
             "observed_at": datetime.now(timezone.utc).isoformat()}
    observation = {
        "schema_version": 1, "inventory_phase": phase,
        "identity": {
            "application_uri": "UA_URI_SENTINEL",
            "product_uri": "UA_PRODUCT_SENTINEL",
            "application_name": "UA_APP_SENTINEL",
            "application_type": "Server",
        },
        "certificate_sha256": "b" * 64,
        "endpoints": [{
            "endpoint_url": "opc.tcp://user:UA_SECRET_SENTINEL@192.168.1.10:4840/path",
            "security_policy_uri": "UA_POLICY_SENTINEL",
            "security_mode": "None",
            "transport_profile_uri": "UA_PROFILE_SENTINEL",
            "security_level": 0,
            "user_token_count": 1,
            "user_token_types": ["Anonymous"],
            "target_matches": True,
        }],
        "mapping": {"phase": phase, "nodes": [{"node_id": "UA_NODE_SENTINEL",
                    "parent_node_id": None, "depth": 0, "node_class": "Variable",
                    "browse_name": "UA_BROWSE_SENTINEL",
                    "display_name": "UA_DISPLAY_SENTINEL",
                    "data_type": "UA_TYPE_SENTINEL", "value_rank": -1,
                    "access_level": 3,
                    "user_access_level": 3, "value_read_status": "Good"}],
                    "references": [], "references_observed": 0,
                    "value_reads_attempted": 1,
                    "selected_endpoint_index": 0, "anonymous_session_activated": True,
                    "browse_succeeded": True, "application_value_read_succeeded": True,
                    "value_good_count": 1,
                    "security_mode": {
                        "value": "None", "source": "get_endpoints", "status": "Good",
                    },
                    "security_policy": {
                        "value": "None", "source": "get_endpoints", "status": "Good",
                    }},
    }
    administrative_session.add_all([
        IndustrialServiceRecord(scan_host_id=seeded["scan_host"].id,
                                protocol="modbus_tcp", port=502, confidence="confirmed",
                                evidence_sources_json=["response"]),
        IndustrialServiceRecord(scan_host_id=seeded["scan_host"].id,
                                protocol="opcua_tcp", port=4840, confidence="confirmed",
                                evidence_sources_json=["valid_response"],
                                opcua_observation_json=observation),
        IndustrialServiceRecord(scan_host_id=seeded["scan_host"].id,
                                protocol="opcua_tcp", port=4841, confidence="confirmed",
                                evidence_sources_json=["valid_response"],
                                opcua_observation_json={
                                    **observation, "mapping": None,
                                }),
    ])
    administrative_session.commit()

    context = build_scan_ai_context(administrative_session, seeded["scan"])
    assert context is not None
    assert context.context_version == "6"
    assert context.industrial_protocols.modbus_tcp.service_count == 1
    ua = context.industrial_protocols.opcua_tcp
    assert ua.service_count == ua.confirmed_services == 2
    assert ua.mapping_not_attempted == 1
    assert ua.anonymous_read_verified == 1
    serialized = context.model_dump_json()
    for sentinel in ("UA_NODE_SENTINEL", "UA_SECRET_SENTINEL", "UA_URI_SENTINEL",
                     "UA_PRODUCT_SENTINEL", "UA_APP_SENTINEL", "UA_POLICY_SENTINEL",
                     "UA_PROFILE_SENTINEL", "UA_BROWSE_SENTINEL", "UA_DISPLAY_SENTINEL",
                     "UA_TYPE_SENTINEL", "b" * 64):
        assert sentinel not in serialized


@pytest.mark.parametrize(
    "mapping_source", [None, "service_granularity", "discovery_only"]
)
def test_modbus_discovery_units_are_not_counted_as_mapping_in_ai_context(
    mapping_source,
):
    service = SimpleNamespace(
        protocol="modbus_tcp", confidence="confirmed",
        mapping_source=mapping_source,
        units=[SimpleNamespace(status="responding") for _ in range(3)],
    )
    modbus = summarize_industrial_protocols([service]).modbus_tcp
    assert modbus.service_count == 1
    assert modbus.mapping_not_attempted == 1
    assert modbus.mapping_completed == modbus.mapping_limited == 0


@pytest.mark.parametrize(
    ("method", "status", "confidence", "truncated", "source", "basis"),
    [
        ("unknown", "unknown", None, False, "legacy", "unknown"),
        (
            "specific_check", "inconclusive", "tentative", False,
            "nse", "target_observation",
        ),
        (
            "configuration_observation", "conflicting", "tentative", False,
            "nse", "target_observation",
        ),
        (
            "version_correlation", "supported", "probable", False,
            "nvd_enrichment", "cve_correlation",
        ),
        ("specific_check", "supported", "confirmed", True, "nse", "target_observation"),
    ],
)
def test_finding_context_preserves_evidence_limits_without_raw_fields(
    administrative_session, method, status, confidence, truncated, source, basis
):
    seeded = seed_read_graph(administrative_session)
    detail = get_scan_detail(
        administrative_session, seeded["scan"].scan_id, org_id=seeded["org"].id
    )
    assert detail is not None
    evidence_observations = [{
        "condition_key": "CVE-2024-10001",
        "method": method,
        "result": "inconclusive",
        "source": source,
        "source_script": "RAW_SCRIPT_SENTINEL",
        "rule_id": "RAW_RULE_SENTINEL",
        "rule_version": "1",
        "evidence": "RAW_OBSERVATION_SENTINEL",
        "facts": {"RAW_FACT_KEY_SENTINEL": "RAW_FACT_VALUE_SENTINEL"},
    }] if basis != "unknown" else []
    finding = detail.findings[0].model_copy(
        update={
            "title": "RAW_TITLE_SENTINEL",
            "evidence": "RAW_EVIDENCE_SENTINEL",
            "source": source,
            "cve_id": "CVE-2024-10001" if method == "version_correlation" else None,
            "detection_method": method,
            "evidence_status": status,
            "confidence": confidence,
            "evidence_truncated": truncated,
            "evidence_observations": evidence_observations,
        }
    )
    bundle = build_finding_contexts([finding], machine_refs={})
    context = bundle.contexts[0]

    assert context.evidence_basis == basis
    assert context.detection_method == method
    assert context.evidence_status == status
    assert context.evidence_truncated is truncated
    serialized = context.model_dump_json()
    for raw_value in (
        "RAW_TITLE_SENTINEL", "RAW_EVIDENCE_SENTINEL", "RAW_SCRIPT_SENTINEL",
        "RAW_RULE_SENTINEL", "RAW_OBSERVATION_SENTINEL",
        "RAW_FACT_KEY_SENTINEL", "RAW_FACT_VALUE_SENTINEL",
    ):
        assert raw_value not in serialized


def test_materialize_analysis_replaces_local_references(administrative_session):
    seeded = seed_read_graph(administrative_session)
    context = build_scan_ai_context(administrative_session, seeded["scan"])
    assert context is not None

    analysis = materialize_scan_ai_analysis(
        context,
        ProviderScanAIAnalysis(
            executive_summary="finding_1 needs attention.",
            overall_assessment="machine_1 has one recorded vulnerability.",
            plain_language_summary="Review finding_1 with the machine owner.",
            priority_actions=[
                AIProviderRecommendedAction(
                    priority="high",
                    title="Review finding_1",
                    description="Ask the owner of machine_1 to review it.",
                    related_finding_refs=["finding_1"],
                )
            ],
            important_findings=[
                AIProviderFindingExplanation(
                    finding_ref="finding_1",
                    why_it_matters="finding_1 is exposed.",
                    plain_language_explanation="machine_1 needs a review.",
                    recommendation="Review finding_1.",
                    evidence_used=["The scan recorded finding_1."],
                    uncertainty=None,
                )
            ],
            uncertainties=[],
        ),
    )

    assert analysis.important_findings[0].finding_id == seeded["finding"].finding_id
    assert analysis.priority_actions[0].related_finding_ids == [
        seeded["finding"].finding_id
    ]
    assert "finding_1" not in analysis.model_dump_json()
    assert "machine_1" not in analysis.model_dump_json()


def test_materialize_analysis_rejects_unknown_reference(administrative_session):
    seeded = seed_read_graph(administrative_session)
    context = build_scan_ai_context(administrative_session, seeded["scan"])
    assert context is not None

    analysis = ProviderScanAIAnalysis(
        executive_summary="finding_99 needs attention.",
        overall_assessment="The scan recorded a vulnerability.",
        plain_language_summary="Review the recorded vulnerability.",
        priority_actions=[],
        important_findings=[],
        uncertainties=[],
    )

    with pytest.raises(ValueError, match="unknown reference"):
        materialize_scan_ai_analysis(context, analysis)


def test_context_requires_completed_scan(administrative_session):
    seeded = seed_read_graph(administrative_session)
    seeded["scan"].status = "processing"
    administrative_session.add(seeded["scan"])
    administrative_session.commit()

    with pytest.raises(ScanAINotReadyError):
        build_scan_ai_context(administrative_session, seeded["scan"])


def test_split_context_keeps_full_evidence_summary(administrative_session):
    seeded = seed_read_graph(administrative_session)
    context = build_scan_ai_context(administrative_session, seeded["scan"])
    assert context is not None
    context.top_findings = [
        context.top_findings[0],
        context.top_findings[0].model_copy(update={"finding_ref": "finding_2"}),
    ]
    context._finding_ids_by_ref["finding_2"] = seeded["other_finding"].finding_id
    context._display_values_by_ref["finding_2"] = "Second finding"

    chunks = split_context(context, child_findings=1)

    assert len(chunks) == 2
    assert [chunk.top_findings[0].finding_ref for chunk in chunks] == [
        "finding_1", "finding_2"
    ]
    assert all(chunk.evidence_summary == context.evidence_summary for chunk in chunks)
    assert all(chunk.context_version == "6" for chunk in chunks)


@pytest.mark.parametrize("max_findings", [0, 16])
def test_context_rejects_invalid_finding_limit(
    administrative_session,
    max_findings,
):
    seeded = seed_read_graph(administrative_session)

    with pytest.raises(ValueError, match="max_findings must be between 1 and 15"):
        build_scan_ai_context(
            administrative_session,
            seeded["scan"],
            max_findings=max_findings,
        )
