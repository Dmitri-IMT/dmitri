# ruff: noqa: E501
from __future__ import annotations

import json

from agent.targeted.executor import ToolExecution
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
)
from agent.targeted.tls import parse_testssl_json, run_testssl


class FakeExecutor:
    def __init__(self, execution: ToolExecution) -> None:
        self.execution = execution
        self.commands = []

    def execute(self, command, **_kwargs):
        self.commands.append(command)
        return self.execution


def unit() -> TargetedUnit:
    return TargetedUnit(
        "192.0.2.10", 443, "tcp", "https", TargetedTool.TESTSSL, "https"
    )


def test_testssl_maps_affirmative_protocol_and_ignores_ok() -> None:
    report = {
        "scanResult": [
            {
                "id": "protocols",
                "ip": "192.0.2.10",
                "port": 443,
                "severity": "HIGH",
                "finding": "TLS 1.0",
            },
            {"id": "cipher", "severity": "OK", "finding": "OK"},
        ]
    }
    issues = parse_testssl_json(report, unit())
    assert [issue.issue_key for issue in issues] == ["tls.protocol:tls1.0"]


def test_testssl_parses_native_nested_host_report_and_inherits_target() -> None:
    report = {
        "scanResult": [
            {
                "ip": "192.0.2.10",
                "port": "443",
                "protocols": [
                    {
                        "id": "protocols",
                        "severity": "HIGH",
                        "finding": "TLS 1.0 offered",
                    }
                ],
                "cert": [
                    {
                        "id": "cert_trust",
                        "severity": "HIGH",
                        "finding": "certificate does not match supplied URI",
                    },
                    {
                        "id": "cert_chain_of_trust",
                        "severity": "CRITICAL",
                        "finding": "failed (self signed).",
                    },
                    {
                        "id": "cert_subjectAltName",
                        "severity": "HIGH",
                        "finding": "No SAN, browsers are complaining",
                    },
                ],
            }
        ]
    }

    issues = parse_testssl_json(report, unit())

    assert [issue.issue_key for issue in issues] == [
        "tls.protocol:tls1.0",
        "tls.certificate:certificate.does.not.match.supplied.uri",
        "tls.certificate:self-signed",
        "tls.certificate:no.san.browsers.are.complaining",
    ]


def test_testssl_marks_exit_code_with_scan_errors_as_failed() -> None:
    execution = ToolExecution(
        TargetedOutcome.COMPLETED,
        exit_code=7,
        report=json.dumps({"scanResult": []}).encode(),
        report_present=True,
    )
    executor = FakeExecutor(execution)
    result = run_testssl(unit(), executor)
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.EXECUTION_ERROR
    assert executor.commands[0].argv[1:] == [
        "--warnings",
        "batch",
        "--color",
        "0",
        "--connect-timeout",
        "5",
        "--openssl-timeout",
        "5",
        "--protocols",
        "--server-defaults",
        "--header",
        "--vulnerable",
        "--jsonfile-pretty",
        "REPORT",
        "192.0.2.10:443",
    ]
    assert executor.commands[0].report_mode == "file"
    assert executor.commands[0].report_argument_index == 14


def test_testssl_preserves_partial_findings_when_report_marks_scan_problem() -> None:
    report = {
        "scanResult": [
            {
                "id": "protocols",
                "severity": "HIGH",
                "finding": "TLS 1.0 offered",
            },
            {
                "id": "scanProblem",
                "severity": "FATAL",
                "finding": "No server certificate could be retrieved",
            },
        ]
    }
    result = run_testssl(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                exit_code=246,
                report=json.dumps(report).encode(),
                report_present=True,
            )
        ),
    )

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.EXECUTION_ERROR
    assert [issue.issue_key for issue in result.issues] == ["tls.protocol:tls1.0"]


def test_testssl_keeps_vulnerability_score_exit_codes_completed() -> None:
    result = run_testssl(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                exit_code=50,
                report=json.dumps(
                    {
                        "scanResult": [
                            {
                                "id": "protocols",
                                "severity": "HIGH",
                                "finding": "TLS 1.0 offered",
                            }
                        ]
                    }
                ).encode(),
                report_present=True,
            )
        ),
    )

    assert result.outcome == TargetedOutcome.COMPLETED
    assert [issue.issue_key for issue in result.issues] == ["tls.protocol:tls1.0"]


def test_testssl_ignores_non_affirmative_and_unknown_records() -> None:
    report = {
        "scanResult": [
            {"id": "protocols", "severity": "INFO", "finding": "TLS 1.0 supported"},
            {"id": "protocols", "severity": "WARN", "finding": "TLS 1.1 supported"},
            {
                "id": "unknown-new-check",
                "severity": "HIGH",
                "finding": "unexpected result",
            },
        ]
    }
    assert parse_testssl_json(report, unit()) == []


def test_testssl_never_maps_scan_problem_records_to_findings() -> None:
    report = {
        "scanResult": [
            {
                "id": "scanProblem",
                "severity": "HIGH",
                "finding": "TLS 1.0 checks could not complete",
            }
        ]
    }

    assert parse_testssl_json(report, unit()) == []


def test_testssl_malformed_and_wrong_target_reports_are_failed() -> None:
    malformed = FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=7,
            report=b"not-json",
            report_present=True,
        )
    )
    malformed_result = run_testssl(unit(), malformed)
    assert malformed_result.outcome == TargetedOutcome.FAILED
    assert malformed_result.reason_code == TargetedGapReason.MALFORMED_REPORT

    wrong_target = FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=7,
            report=json.dumps(
                {
                    "scanResult": [
                        {
                            "id": "protocols",
                            "ip": "192.0.2.11",
                            "port": 443,
                            "severity": "HIGH",
                            "finding": "TLS 1.0",
                        }
                    ]
                }
            ).encode(),
            report_present=True,
        )
    )
    wrong_target_result = run_testssl(unit(), wrong_target)
    assert wrong_target_result.outcome == TargetedOutcome.FAILED
    assert wrong_target_result.reason_code == TargetedGapReason.WRONG_TARGET


def test_testssl_does_not_accept_host_substrings() -> None:
    report = {
        "scanResult": [
            {
                "id": "protocols",
                "ip": "192.0.2.1",
                "port": 443,
                "severity": "HIGH",
                "finding": "TLS 1.0",
            }
        ]
    }
    result = run_testssl(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps(report).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET


def test_testssl_missing_report_is_not_clean_coverage() -> None:
    executor = FakeExecutor(ToolExecution(TargetedOutcome.COMPLETED, exit_code=0))
    result = run_testssl(unit(), executor)
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT


def test_testssl_preserves_timeout_when_report_is_partial() -> None:
    executor = FakeExecutor(
        ToolExecution(
            TargetedOutcome.TIMED_OUT,
            reason_code=TargetedGapReason.UNIT_TIMEOUT,
            report=b'{"scanResult":[',
            report_present=True,
        )
    )

    result = run_testssl(unit(), executor)

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT


def test_testssl_incomplete_scan_record_is_malformed() -> None:
    executor = FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=json.dumps({"scanResult": [{"id": "protocols"}]}).encode(),
            report_present=True,
        )
    )
    result = run_testssl(unit(), executor)
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT
