"""Offline regression corpus for evidence interpretation (not scan accuracy)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest
from agent.normalize.findings import (
    assess_local_evidence,
    extract_findings_and_observations,
)
from agent.scanner.models import HostInfo, PortInfo, ScriptResult, ServiceInfo

FIXTURES = Path(__file__).parent / "fixtures" / "finding_evidence_quality"
EVALUABLE_LABELS = {"positive", "negative"}
MIN_NEGATIVE_REFERENCES_FOR_FP_RATE = 10
PINNED_BASELINE_SHA256 = (
    "ed2bef9dee45776834605910c59a14bf3381bc85cd681ea452e76674407816f4"
)


def _load(split: str) -> dict[str, Any]:
    data = json.loads((FIXTURES / f"{split}.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["split"] == split
    assert data["baseline"]["id"] == "findings-extractor-471739f"
    assert data["baseline"]["source_revision"] == "471739f"
    assert data["baseline"]["artifact"] == "baseline-471739f.json"
    assert data["notes"]["sample_size"] == len(data["cases"])
    assert data["notes"]["limitations"]
    return data


def _host(case: dict[str, Any]) -> HostInfo:
    item = case["input"]
    port = PortInfo(
        port=item["port"],
        protocol=item["protocol"],
        service=ServiceInfo(name=item["service"], cpes=item.get("cpes", [])),
        scripts=[
            ScriptResult(
                script_id=case["origin"]["script"],
                output=item.get("output", ""),
                data=item.get("data"),
            )
        ],
    )
    return HostInfo(ip=item["ip"], hostname="fixture-host", ports=[port])


def _current_result(case: dict[str, Any]) -> tuple[str, str | None]:
    findings, observations, _ = extract_findings_and_observations([_host(case)])
    assessments = [assess_local_evidence(item) for item in findings]
    direct_positive = next(
        (
            item
            for item in assessments
            if item.status == "supported"
            and item.confidence == "confirmed"
            and item.method in {"configuration_observation", "specific_check"}
        ),
        None,
    )
    if direct_positive is not None:
        return "positive", direct_positive.method
    negative = next((item for item in observations if item.result == "negative"), None)
    if negative is not None:
        return "negative", negative.method
    if findings:
        method = assessments[0].method if assessments else None
        return "inconclusive", method
    if observations:
        return "inconclusive", observations[0].method
    return "not_evaluable", None


def _baseline_predictions(cases: list[dict[str, Any]]) -> dict[str, str]:
    """Load pinned pre-change outputs and verify each output belongs to its input."""
    baseline = json.loads(
        (FIXTURES / "baseline-471739f.json").read_text(encoding="utf-8")
    )
    assert baseline["source_revision"] == "471739f"
    assert baseline["source_sha256"] == PINNED_BASELINE_SHA256
    assert baseline["implementation"].endswith(":extract_findings")
    assert baseline["prediction_rule"].startswith("positive iff")
    case_by_id = {case["id"]: case for case in cases}
    records = {record["case_id"]: record for record in baseline["records"]}
    assert records.keys() == case_by_id.keys()

    predictions = {}
    for case_id, case in case_by_id.items():
        record = records[case_id]
        digest = hashlib.sha256(
            json.dumps(case, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        assert record["case_sha256"] == digest
        assert record["finding_count"] == len(record["findings"])
        assert record["prediction"] == (
            "positive" if record["finding_count"] else "negative"
        )
        predictions[case_id] = record["prediction"]
    return predictions


def _corpus_metrics(
    cases: list[dict[str, Any]], *, use_current: bool
) -> dict[str, Any]:
    confusion: Counter[str] = Counter()
    unresolved = 0
    unresolved_positive = 0
    evaluable = 0
    reference_inconclusive = 0
    reference_not_evaluable = 0
    current_inconclusive_predictions = 0
    current_no_record_predictions = 0
    by_method: dict[str, Counter[str]] = defaultdict(Counter)

    baseline_predictions = _baseline_predictions(cases) if not use_current else {}
    for case in cases:
        label = case["reference_label"]
        if label == "inconclusive":
            reference_inconclusive += 1
        elif label == "not_evaluable":
            reference_not_evaluable += 1

        method = "findings-extractor-471739f" if not use_current else "no_record"
        prediction = (
            baseline_predictions[case["id"]] if not use_current else "no_record"
        )
        if use_current:
            prediction, current_method = _current_result(case)
            method = current_method or "no_record"
            current_inconclusive_predictions += prediction == "inconclusive"
            current_no_record_predictions += prediction == "not_evaluable"
            by_method[method]["prediction_inconclusive"] += prediction == "inconclusive"
            by_method[method]["prediction_not_evaluable"] += (
                prediction == "not_evaluable"
            )

        if label not in EVALUABLE_LABELS:
            by_method[method]["reference_inconclusive"] += label == "inconclusive"
            by_method[method]["reference_not_evaluable"] += label == "not_evaluable"
            continue

        evaluable += 1
        if prediction in {"inconclusive", "not_evaluable"}:
            unresolved += 1
            unresolved_positive += label == "positive"
            by_method[method]["unresolved"] += 1
            continue

        key = {
            ("positive", "positive"): "tp",
            ("negative", "positive"): "fp",
            ("positive", "negative"): "fn",
            ("negative", "negative"): "tn",
        }[(label, prediction)]
        confusion[key] += 1
        by_method[method][key] += 1

    tp, fp, fn, tn = (confusion[key] for key in ("tp", "fp", "fn", "tn"))
    predicted_positive = tp + fp
    decisive = tp + fp + fn + tn
    negatives = sum(case["reference_label"] == "negative" for case in cases)
    fp_rate = (
        {"numerator": fp, "denominator": fp + tn, "value": fp / (fp + tn)}
        if negatives >= MIN_NEGATIVE_REFERENCES_FOR_FP_RATE and fp + tn
        else None
    )
    return {
        "cases": len(cases),
        "reference_evaluable": evaluable,
        "reference_inconclusive": reference_inconclusive,
        "reference_not_evaluable": reference_not_evaluable,
        "current_inconclusive_predictions": current_inconclusive_predictions,
        "current_no_record_predictions": current_no_record_predictions,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "unresolved_predictions": unresolved,
        "unresolved_positive_references": unresolved_positive,
        "precision": {
            "numerator": tp,
            "denominator": predicted_positive,
            "value": tp / predicted_positive if predicted_positive else None,
        },
        "coverage": {
            "numerator": decisive,
            "denominator": evaluable,
            "value": decisive / evaluable if evaluable else None,
        },
        "false_positive_rate": fp_rate,
        "false_positive_rate_suppressed_reason": (
            None
            if fp_rate is not None
            else (
                f"requires at least {MIN_NEGATIVE_REFERENCES_FOR_FP_RATE} "
                f"negative references; found {negatives}"
            )
        ),
        "by_method": {
            method: dict(counts) for method, counts in sorted(by_method.items())
        },
    }


def _validate_case(case: dict[str, Any]) -> None:
    assert case["id"]
    assert case["origin"]["tool"]
    assert case["origin"]["version"]
    assert case["origin"]["script"]
    assert case["condition"]
    assert case["reference_label"] in {
        "positive",
        "negative",
        "inconclusive",
        "not_evaluable",
    }
    assert case["expected_current"] in {
        "positive",
        "negative",
        "inconclusive",
        "not_evaluable",
    }
    assert case["input"]["ip"].startswith("192.0.2.")


@pytest.mark.parametrize("split", ["development", "evaluation"])
def test_versioned_offline_corpus_cases_match_current_parser(split: str) -> None:
    corpus = _load(split)
    ids = [case["id"] for case in corpus["cases"]]
    assert len(ids) == len(set(ids))

    for case in corpus["cases"]:
        _validate_case(case)
        actual, method = _current_result(case)
        assert actual == case["expected_current"], case["id"]
        if case["expected_method"] is not None:
            assert method == case["expected_method"], case["id"]


def test_development_and_evaluation_splits_do_not_share_examples() -> None:
    development = _load("development")["cases"]
    evaluation = _load("evaluation")["cases"]
    development_ids = {case["id"] for case in development}
    evaluation_ids = {case["id"] for case in evaluation}

    assert development_ids.isdisjoint(evaluation_ids)
    assert {_canonical_case_content(case) for case in development}.isdisjoint(
        {_canonical_case_content(case) for case in evaluation}
    )


def _canonical_case_content(case: dict[str, Any]) -> str:
    """Compare case meaning without IDs or synthetic IPs distinguishing it."""
    content = json.loads(json.dumps(case))
    content.pop("id")
    content["input"].pop("ip")
    return json.dumps(content, sort_keys=True, separators=(",", ":"))


def test_repeated_positive_witness_does_not_raise_confidence() -> None:
    corpus = _load("evaluation")
    repeated = next(
        case
        for case in corpus["cases"]
        if case["id"] == "eval-repeated-positive-witness"
    )
    single = next(
        case for case in corpus["cases"] if case["id"] == "eval-ms17-positive-control"
    )
    repeated_findings, _, _ = extract_findings_and_observations([_host(repeated)])
    single_findings, _, _ = extract_findings_and_observations([_host(single)])
    repeated_assessment = assess_local_evidence(repeated_findings[0])
    single_assessment = assess_local_evidence(single_findings[0])

    assert (
        repeated_assessment.method,
        repeated_assessment.status,
        repeated_assessment.confidence,
    ) == (
        single_assessment.method,
        single_assessment.status,
        single_assessment.confidence,
    )
    assert repeated_assessment.confidence == "confirmed"


def test_evaluation_reports_baseline_and_current_with_explicit_denominators(
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = _load("evaluation")
    cases = corpus["cases"]
    baseline = _corpus_metrics(cases, use_current=False)
    current = _corpus_metrics(cases, use_current=True)

    assert baseline["cases"] == current["cases"] == len(cases)
    assert baseline["reference_evaluable"] == current["reference_evaluable"]
    assert current["reference_inconclusive"] == 5
    assert current["reference_not_evaluable"] == 1
    assert current["current_no_record_predictions"] == 1
    assert current["current_inconclusive_predictions"] == 5
    assert baseline["false_positive_rate"] is None
    assert current["false_positive_rate"] is None
    assert baseline["tp"] == 2
    assert baseline["fp"] == 1
    assert baseline["fn"] == 3
    assert (
        "requires at least 10 negative references"
        in current["false_positive_rate_suppressed_reason"]
    )
    assert baseline["fp"] > current["fp"]
    assert current["tp"] >= 2
    assert current["current_inconclusive_predictions"] > 0
    assert current["unresolved_positive_references"] == 0
    assert current["precision"]["denominator"] == current["tp"] + current["fp"]
    assert current["coverage"]["denominator"] == current["reference_evaluable"]
    assert "configuration_observation" in current["by_method"]
    assert "specific_check" in current["by_method"]

    print(
        json.dumps(
            {"baseline": baseline, "current": current},
            indent=2,
            sort_keys=True,
        )
    )
    assert capsys.readouterr().out
