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
    return TargetedUnit("192.0.2.10", 443, "tcp", "https", TargetedTool.TESTSSL, "https")


def test_testssl_maps_affirmative_protocol_and_ignores_ok() -> None:
    report = {"scanResult": [{"id": "protocols", "ip": "192.0.2.10", "port": 443, "severity": "HIGH", "finding": "TLS 1.0"}, {"id": "cipher", "severity": "OK", "finding": "OK"}]}
    issues = parse_testssl_json(report, unit())
    assert [issue.issue_key for issue in issues] == ["tls.protocol:tls1.0"]


def test_testssl_uses_safe_argv_and_accepts_nonzero_exit() -> None:
    execution = ToolExecution(TargetedOutcome.COMPLETED, exit_code=7, report=json.dumps({"scanResult": []}).encode(), report_present=True)
    executor = FakeExecutor(execution)
    result = run_testssl(unit(), executor)
    assert result.outcome == TargetedOutcome.COMPLETED
    assert executor.commands[0].argv[1:] == ["--warnings", "batch", "--color", "0", "--socket-timeout", "5", "--openssl-timeout", "5", "--jsonfile-pretty", "REPORT", "192.0.2.10:443"]
    assert executor.commands[0].report_mode == "file"
    assert executor.commands[0].report_argument_index == 10


def test_testssl_ignores_non_affirmative_and_unknown_records() -> None:
    report = {
        "scanResult": [
            {"id": "protocols", "severity": "INFO", "finding": "TLS 1.0 supported"},
            {"id": "protocols", "severity": "WARN", "finding": "TLS 1.1 supported"},
            {"id": "unknown-new-check", "severity": "HIGH", "finding": "unexpected result"},
        ]
    }
    assert parse_testssl_json(report, unit()) == []


def test_testssl_malformed_and_wrong_target_reports_are_failed() -> None:
    malformed = FakeExecutor(
        ToolExecution(TargetedOutcome.COMPLETED, exit_code=7, report=b"not-json", report_present=True)
    )
    malformed_result = run_testssl(unit(), malformed)
    assert malformed_result.outcome == TargetedOutcome.FAILED
    assert malformed_result.reason_code == TargetedGapReason.MALFORMED_REPORT

    wrong_target = FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=7,
            report=json.dumps(
                {"scanResult": [{"id": "protocols", "ip": "192.0.2.11", "port": 443, "severity": "HIGH", "finding": "TLS 1.0"}]}
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
            {"id": "protocols", "ip": "192.0.2.1", "port": 443, "severity": "HIGH", "finding": "TLS 1.0"}
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
