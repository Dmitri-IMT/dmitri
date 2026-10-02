from __future__ import annotations

import pytest
from api.services.command_lifecycle import (
    NON_TERMINAL,
    PI_OWNED,
    RANK,
    TERMINAL,
    is_terminal,
    scan_status_for,
    status_rank,
)

STATUSES = [
    "queued",
    "delivered",
    "running",
    "uploading",
    "done",
    "failed",
    "cancelled",
    "expired",
]


def test_rank_covers_every_status():
    assert set(RANK) == set(STATUSES)


def test_non_terminal_is_rank_ordered_and_excludes_terminal():
    assert NON_TERMINAL == ("queued", "delivered", "running", "uploading")
    assert not set(NON_TERMINAL) & TERMINAL


def test_pi_owned_statuses_outrank_delivered():
    assert all(status_rank(s) > status_rank("delivered") for s in PI_OWNED)
    assert "cancelled" in PI_OWNED


def test_terminal_statuses_share_the_top_rank():
    assert {status_rank(s) for s in TERMINAL} == {max(RANK.values())}


@pytest.mark.parametrize("status", ["done", "failed", "cancelled", "expired"])
def test_is_terminal_true_for_terminal_statuses(status):
    assert is_terminal(status) is True


@pytest.mark.parametrize("status", ["queued", "delivered", "running", "uploading"])
def test_is_terminal_false_for_non_terminal_statuses(status):
    assert is_terminal(status) is False


@pytest.mark.parametrize(
    "command_status,expected_scan_status",
    [
        ("queued", "pending"),
        ("delivered", "pending"),
        ("running", "accepted"),
        ("uploading", "processing"),
        ("done", "completed"),
        ("failed", "failed"),
        ("cancelled", "cancelled"),
        ("expired", "failed"),
    ],
)
def test_scan_status_for_projects_command_status(command_status, expected_scan_status):
    assert scan_status_for(command_status) == expected_scan_status


def test_scan_status_for_is_pure_projection():
    before = "running"
    result = scan_status_for(before)
    assert scan_status_for(before) == result
