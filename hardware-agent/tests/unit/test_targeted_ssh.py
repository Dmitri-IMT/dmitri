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
from agent.targeted.ssh import parse_ssh_audit_json, run_ssh_audit


class FakeExecutor:
    def __init__(self, execution: ToolExecution) -> None:
        self.execution = execution
        self.commands = []

    def execute(self, command, **_kwargs):
        self.commands.append(command)
        return self.execution


def unit() -> TargetedUnit:
    return TargetedUnit("192.0.2.10", 22, "tcp", "ssh", TargetedTool.SSH_AUDIT)


def test_ssh_maps_fail_and_ignores_post_quantum_advice() -> None:
    report = {"target": "192.0.2.10:22", "kex": {"diffie-hellman-group1-sha1": {"fail": ["weak algorithm"], "warn": ["does not provide protection against post-quantum attacks"]}}}
    issues = parse_ssh_audit_json(report, unit())
    assert [issue.issue_key for issue in issues] == ["ssh.algorithm:kex:diffie-hellman-group1-sha1"]
    assert "post-quantum" not in issues[0].evidence


def test_ssh_maps_warn_and_cve_score_to_severity() -> None:
    report = {
        "target": {"host": "192.0.2.10", "port": 22},
        "cipher": {
            "3des-cbc": {
                "warn": ["legacy cipher"],
                "cve": "CVE-2024-1234",
                "cvss": 7.5,
            }
        },
    }
    issues = parse_ssh_audit_json(report, unit())
    assert len(issues) == 1
    assert issues[0].issue_key == "ssh.algorithm:cipher:3des-cbc"
    assert issues[0].severity == "high"
    assert issues[0].cve_id == "CVE-2024-1234"


def test_ssh_cvss_below_four_is_low() -> None:
    report = {
        "target": "192.0.2.10:22",
        "cipher": {"legacy": {"warn": ["weak cipher"], "cvss": 3.9}},
    }
    issues = parse_ssh_audit_json(report, unit())
    assert len(issues) == 1
    assert issues[0].severity == "low"


def test_ssh_info_only_and_unknown_algorithm_are_not_findings() -> None:
    report = {
        "target": "192.0.2.10:22",
        "kex": {
            "curve25519-sha256": {"info": ["preferred"]},
            "vendor-extension": {"warn": []},
        },
        "banner": {"version": "OpenSSH_9.0"},
    }
    assert parse_ssh_audit_json(report, unit()) == []


def test_ssh_unknown_algorithm_with_fail_or_warn_is_not_a_finding() -> None:
    report = {
        "target": "192.0.2.10:22",
        "kex": {"unknown-algorithm": {"fail": ["unsupported schema mapping"]}},
        "cipher": {"vendor-extension": {"warn": ["not a supported primitive"]}},
    }
    assert parse_ssh_audit_json(report, unit()) == []


def test_ssh_unknown_schema_subtree_is_not_a_finding() -> None:
    report = {
        "target": "192.0.2.10:22",
        "kex": {"unknown": {"foo": {"fail": ["bad"]}}},
    }
    assert parse_ssh_audit_json(report, unit()) == []


def test_ssh_malformed_and_unknown_notes_are_safe() -> None:
    report = {
        "target": "192.0.2.10:22",
        "kex": {
            "malformed": {"fail": {"not": "a note"}, "warn": [None, 7]},
            "empty": {"fail": [], "warn": []},
        },
    }
    assert parse_ssh_audit_json(report, unit()) == []


def test_ssh_does_not_accept_host_substrings() -> None:
    report = {
        "target": "192.0.2.1:22",
        "kex": {"weak": {"fail": ["obsolete"]}},
    }
    assert parse_ssh_audit_json(report, unit()) == []


def test_ssh_recognized_malformed_schema_fails() -> None:
    result = run_ssh_audit(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps({"target": "192.0.2.10:22", "kex": []}).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT


def test_ssh_uses_audit_only_argv() -> None:
    execution = ToolExecution(TargetedOutcome.COMPLETED, report=json.dumps({"target": "192.0.2.10:22"}).encode(), report_present=True)
    executor = FakeExecutor(execution)
    result = run_ssh_audit(unit(), executor)
    assert result.outcome == TargetedOutcome.COMPLETED
    assert executor.commands[0].argv == ("ssh-audit", "-j", "-t", "5", "--skip-rate-test", "-p", "22", "192.0.2.10") or list(executor.commands[0].argv) == ["ssh-audit", "-j", "-t", "5", "--skip-rate-test", "-p", "22", "192.0.2.10"]
    assert not {"--client", "--policy", "--gex", "--dheat", "--rate-test", "-u"}.intersection(executor.commands[0].argv)


def test_ssh_malformed_and_wrong_target_reports_fail() -> None:
    malformed = run_ssh_audit(
        unit(), FakeExecutor(ToolExecution(TargetedOutcome.COMPLETED, report=b"not-json", report_present=True))
    )
    assert malformed.outcome == TargetedOutcome.FAILED
    assert malformed.reason_code == TargetedGapReason.MALFORMED_REPORT

    wrong_target = run_ssh_audit(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps({"target": "192.0.2.11:22", "kex": {}}).encode(),
                report_present=True,
            )
        ),
    )
    assert wrong_target.outcome == TargetedOutcome.FAILED
    assert wrong_target.reason_code == TargetedGapReason.WRONG_TARGET


def test_ssh_valid_nonzero_exit_completes() -> None:
    execution = ToolExecution(
        TargetedOutcome.COMPLETED,
        exit_code=2,
        report=json.dumps({"target": "192.0.2.10:22", "protocol": {"ssh1": {"fail": ["obsolete"]}}}).encode(),
        report_present=True,
    )
    result = run_ssh_audit(unit(), FakeExecutor(execution))
    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.exit_code == 2
    assert result.issues[0].severity == "high"
