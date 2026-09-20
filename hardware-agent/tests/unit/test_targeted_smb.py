# ruff: noqa: E501
from __future__ import annotations

import json

import pytest
from agent.targeted.executor import ToolExecution
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
)
from agent.targeted.smb import parse_enum4linux_json, run_enum4linux


class FakeExecutor:
    def __init__(self, execution: ToolExecution) -> None:
        self.execution = execution
        self.commands = []

    def execute(self, command, **_kwargs):
        self.commands.append(command)
        return self.execution


def unit() -> TargetedUnit:
    return TargetedUnit("192.0.2.10", 445, "tcp", "microsoft-ds", TargetedTool.ENUM4LINUX)


def test_enum4linux_maps_null_session_and_bounded_share() -> None:
    report = {"target": "192.0.2.10", "sessions": {"null_session": True}, "shares": [{"name": "public", "access": {"mapping": "ok", "listing": "ok"}}]}
    issues = parse_enum4linux_json(report, unit())
    assert {issue.issue_key for issue in issues} == {"smb:anonymous-session", "smb:anonymous-share:public"}


def test_enum4linux_argv_has_no_credentials() -> None:
    execution = ToolExecution(TargetedOutcome.COMPLETED, exit_code=1, report=json.dumps({"target": "192.0.2.10"}).encode(), report_present=True)
    executor = FakeExecutor(execution)
    result = run_enum4linux(unit(), executor)
    assert result.outcome == TargetedOutcome.COMPLETED
    assert executor.commands[0].argv == ["enum4linux-ng", "-As", "-t", "5", "-oJ", "REPORT", "192.0.2.10"]
    assert executor.commands[0].report_mode == "file"
    assert executor.commands[0].report_argument_index == 5
    assert executor.commands[0].report_path_mode == "base"
    assert not {"-u", "-p", "-K", "-H", "-R", "-s"}.intersection(executor.commands[0].argv)


def test_enum4linux_inventory_is_an_observation_not_a_finding() -> None:
    execution = ToolExecution(
        TargetedOutcome.COMPLETED,
        report=json.dumps(
            {"target": "192.0.2.10", "os_info": {"name": "Windows"}, "shares": [{"name": "public"}], "users": {"users": ["alice"]}}
        ).encode(),
        report_present=True,
    )
    result = run_enum4linux(unit(), FakeExecutor(execution))
    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.issues == []
    assert [item.observation_key for item in result.observations] == ["smb:inventory"]


def test_enum4linux_none_policy_values_map_only_to_numeric_zero() -> None:
    report = {
        "target": "192.0.2.10",
        "password_policy": {
            "minimum_password_length": "None",
            "lockout_threshold": "None",
            "password_complexity": None,
        },
    }
    assert {issue.issue_key for issue in parse_enum4linux_json(report, unit())} == {
        "smb:password-length",
        "smb:lockout-threshold",
    }


def test_enum4linux_missing_or_null_numeric_policy_values_stay_unknown() -> None:
    report = {
        "target": "192.0.2.10",
        "password_policy": {
            "minimum_password_length": None,
            "lockout_threshold": None,
        },
    }
    assert parse_enum4linux_json(report, unit()) == []


def test_enum4linux_ignores_policy_keys_outside_top_level_policy_container() -> None:
    report = {
        "target": "192.0.2.10",
        "unrelated": {
            "password_policy": {
                "minimum_password_length": 1,
                "lockout_threshold": 0,
                "password_complexity": False,
            }
        },
        "shares": [{"name": "public", "metadata": {"access": {"mapping": "ok", "listing": "ok"}}}],
    }
    assert parse_enum4linux_json(report, unit()) == []


def test_enum4linux_policy_numeric_values_are_strict_json_integers() -> None:
    report = {
        "target": "192.0.2.10",
        "password_policy": {
            "minimum_password_length": True,
            "lockout_threshold": 0.0,
            "password_complexity": "false",
            "cleartext_passwords": "true",
        },
    }
    assert parse_enum4linux_json(report, unit()) == []


def test_enum4linux_malformed_and_wrong_target_reports_fail() -> None:
    malformed = run_enum4linux(
        unit(), FakeExecutor(ToolExecution(TargetedOutcome.COMPLETED, report=b"not-json", report_present=True))
    )
    assert malformed.outcome == TargetedOutcome.FAILED
    assert malformed.reason_code == TargetedGapReason.MALFORMED_REPORT

    wrong_target = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps({"target": "192.0.2.11", "shares": []}).encode(),
                report_present=True,
            )
        ),
    )
    assert wrong_target.outcome == TargetedOutcome.FAILED
    assert wrong_target.reason_code == TargetedGapReason.WRONG_TARGET


def test_enum4linux_nonzero_exit_with_valid_report_completes() -> None:
    execution = ToolExecution(
        TargetedOutcome.COMPLETED,
        exit_code=1,
        report=json.dumps({"target": "192.0.2.10", "sessions": {"null_session": True}}).encode(),
        report_present=True,
    )
    result = run_enum4linux(unit(), FakeExecutor(execution))
    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.exit_code == 1
    assert [item.issue_key for item in result.issues] == ["smb:anonymous-session"]


def test_enum4linux_does_not_accept_host_substrings() -> None:
    report = {"target": "192.0.2.1", "sessions": {"null_session": True}}
    assert parse_enum4linux_json(report, unit()) == []


def test_enum4linux_root_target_substring_fails_as_wrong_target() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps({"target": "192.0.2.1", "sessions": {"null_session": True}}).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET


def test_enum4linux_root_direct_port_conflict_fails_as_wrong_target() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps({"target": "192.0.2.10", "port": 139, "sessions": {"null_session": True}}).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET


def test_enum4linux_direct_share_row_port_conflict_fails_as_wrong_target() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps(
                    {
                        "target": "192.0.2.10",
                        "sessions": {"null_session": True},
                        "shares": [{"name": "public", "host": "192.0.2.10", "port": 139}],
                    }
                ).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET


def test_enum4linux_direct_session_row_port_conflict_fails_without_findings() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps(
                    {"target": "192.0.2.10", "sessions": {"null_session": True, "port": 139}}
                ).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET
    assert result.issues == []


def test_enum4linux_direct_share_row_port_conflict_fails_without_findings() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps(
                    {
                        "target": "192.0.2.10",
                        "sessions": {"null_session": True},
                        "shares": [{"name": "public", "port": 139, "access": {"mapping": "ok", "listing": "ok"}}],
                    }
                ).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET
    assert result.issues == []


def test_enum4linux_nested_share_target_conflict_fails_without_findings() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps(
                    {
                        "target": "192.0.2.10",
                        "sessions": {"null_session": True},
                        "shares": [
                            {
                                "name": "public",
                                "target": {"host": "192.0.2.11", "port": 445},
                                "access": {"mapping": "ok", "listing": "ok"},
                            }
                        ],
                    }
                ).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET
    assert result.issues == []


def test_enum4linux_recognized_malformed_schema_fails() -> None:
    result = run_enum4linux(
        unit(),
        FakeExecutor(
            ToolExecution(
                TargetedOutcome.COMPLETED,
                report=json.dumps({"target": "192.0.2.10", "shares": "not-a-list"}).encode(),
                report_present=True,
            )
        ),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT


def test_enum4linux_recognizes_only_approved_top_level_aliases() -> None:
    report = {
        "target": "192.0.2.10",
        "sessions": {"anonymous session": True},
        "shares": [{"sharename": "docs", "access": {"mapping": "ok", "listing": "ok"}}],
        "users": {"user_accounts": ["alice"]},
        "groups": {"group_accounts": ["staff"]},
        "password_policy": {
            "password_min_length": 1,
            "account_lockout_threshold": 0,
            "complexity_enabled": False,
            "cleartext_passwords": True,
        },
    }
    assert {issue.issue_key for issue in parse_enum4linux_json(report, unit())} == {
        "smb:anonymous-session",
        "smb:anonymous-share:docs",
        "smb:anonymous-account-enumeration",
        "smb:password-length",
        "smb:lockout-threshold",
        "smb:password-complexity",
        "smb:passwords-cleartext",
    }


def test_enum4linux_ignores_unknown_nested_evidence_paths() -> None:
    report = {
        "target": "192.0.2.10",
        "sessions": {"metadata": {"guest session": True}},
        "shares": [{"name": "docs", "metadata": {"access": {"mapping": "ok", "listing": "ok"}}}],
        "users": [{"metadata": {"accounts": ["alice"]}}],
        "os_info": {"password_policy": {"minimum_password_length": 1}},
        "errors": [{"sessions": {"null_session": True}}],
    }
    assert parse_enum4linux_json(report, unit()) == []


def test_enum4linux_metadata_mapping_under_account_alias_is_not_counted() -> None:
    report = {
        "target": "192.0.2.10",
        "sessions": {"null_session": True},
        "users": {"users": {"metadata": {"alice": {}}}},
        "groups": {"groups": {"metadata": {"staff": {}}}},
    }
    assert {issue.issue_key for issue in parse_enum4linux_json(report, unit())} == {"smb:anonymous-session"}


def test_enum4linux_account_aliases_are_scoped_to_users_and_groups() -> None:
    report = {
        "target": "192.0.2.10",
        "sessions": {"null_session": True},
        "user_accounts": ["alice"],
        "accounts": ["bob"],
        "group_accounts": ["staff"],
    }
    assert {issue.issue_key for issue in parse_enum4linux_json(report, unit())} == {"smb:anonymous-session"}


@pytest.mark.parametrize("alias", ["null-session", "NULL_SESSION", "guest-session", "GUEST_SESSION"])
def test_enum4linux_session_aliases_are_exact(alias: str) -> None:
    report = {"target": "192.0.2.10", "sessions": {alias: True}}
    assert parse_enum4linux_json(report, unit()) == []


def test_enum4linux_rejects_any_mismatching_target_identity_or_port() -> None:
    for target in (
        {"host": "192.0.2.10", "ip": "192.0.2.11", "port": 445},
        {"host": "192.0.2.10", "ip": "192.0.2.10", "port": 139},
    ):
        result = run_enum4linux(
            unit(),
            FakeExecutor(
                ToolExecution(
                    TargetedOutcome.COMPLETED,
                    report=json.dumps({"target": target, "sessions": {"null_session": True}}).encode(),
                    report_present=True,
                )
            ),
        )
        assert result.outcome == TargetedOutcome.FAILED
        assert result.reason_code == TargetedGapReason.WRONG_TARGET


@pytest.mark.parametrize(
    ("container", "row"),
    [
        ("shares", {"name": "docs", "target": {"host": "192.0.2.11", "port": 445}, "access": {"mapping": "ok", "listing": "ok"}}),
        ("users", {"name": "alice", "target": {"host": "192.0.2.11", "port": 445}}),
        ("groups", {"name": "staff", "target": {"host": "192.0.2.11", "port": 445}}),
    ],
)
def test_enum4linux_recognized_rows_with_target_conflicts_are_rejected(container: str, row: dict) -> None:
    contents = [row] if container == "shares" else {container: [row]}
    report = {"target": "192.0.2.10", container: contents}
    result = run_enum4linux(
        unit(),
        FakeExecutor(ToolExecution(TargetedOutcome.COMPLETED, report=json.dumps(report).encode(), report_present=True)),
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.WRONG_TARGET
    assert result.issues == []


@pytest.mark.parametrize("field", ["minimum_password_length", "lockout_threshold"])
@pytest.mark.parametrize("value", [True, False, 0.0, 7.0, "0", "7", None, "none", " None "])
def test_enum4linux_numeric_policy_values_reject_non_integer_values(field: str, value: object) -> None:
    report = {"target": "192.0.2.10", "password_policy": {field: value}}
    assert parse_enum4linux_json(report, unit()) == []


@pytest.mark.parametrize(
    ("field", "value", "issue_key"),
    [
        ("minimum_password_length", 7, "smb:password-length"),
        ("lockout_threshold", 0, "smb:lockout-threshold"),
        ("minimum_password_length", "None", "smb:password-length"),
        ("lockout_threshold", "None", "smb:lockout-threshold"),
    ],
)
def test_enum4linux_numeric_policy_values_accept_int_and_exact_none(field: str, value: object, issue_key: str) -> None:
    report = {"target": "192.0.2.10", "password_policy": {field: value}}
    assert [issue.issue_key for issue in parse_enum4linux_json(report, unit())] == [issue_key]
