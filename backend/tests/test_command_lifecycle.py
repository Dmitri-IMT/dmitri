from __future__ import annotations

import pytest
from api.services.command_lifecycle import (
    InvalidCommandTransition,
    next_status,
    scan_status_for,
)

STATUSES = ["queued", "delivered", "running", "uploading", "done", "failed", "expired"]

LEGAL_EDGES = [
    ("queued", "delivered"),
    ("queued", "expired"),
    ("delivered", "running"),
    ("delivered", "expired"),
    ("running", "uploading"),
    ("running", "failed"),
    ("uploading", "done"),
    ("uploading", "failed"),
]

ILLEGAL_EDGES = [
    (current, target)
    for current in STATUSES
    for target in STATUSES
    if current != target and (current, target) not in LEGAL_EDGES
]

TERMINAL_STATUSES = ["done", "failed", "expired"]


@pytest.mark.parametrize("current,target", LEGAL_EDGES)
def test_legal_edge_returns_target(current, target):
    assert next_status(current, target) == target


@pytest.mark.parametrize("current,target", ILLEGAL_EDGES)
def test_illegal_edge_raises_with_current_and_target_named(current, target):
    with pytest.raises(InvalidCommandTransition) as excinfo:
        next_status(current, target)
    message = str(excinfo.value)
    assert current in message
    assert target in message


@pytest.mark.parametrize("terminal", TERMINAL_STATUSES)
@pytest.mark.parametrize("target", STATUSES)
def test_terminal_is_hard_sink(terminal, target):
    if target == terminal:
        assert next_status(terminal, target) == terminal
    else:
        with pytest.raises(InvalidCommandTransition):
            next_status(terminal, target)


def test_delivered_to_expired_is_legal():
    assert next_status("delivered", "expired") == "expired"


def test_delivered_to_failed_is_rejected():
    with pytest.raises(InvalidCommandTransition):
        next_status("delivered", "failed")


@pytest.mark.parametrize("status", STATUSES)
def test_duplicate_frame_absorbed(status):
    assert next_status(status, status) == status


@pytest.mark.parametrize(
    "command_status,expected_scan_status",
    [
        ("queued", "pending"),
        ("delivered", "pending"),
        ("running", "accepted"),
        ("uploading", "processing"),
        ("done", "completed"),
        ("failed", "failed"),
        ("expired", "failed"),
    ],
)
def test_scan_status_for_projects_command_status(command_status, expected_scan_status):
    assert scan_status_for(command_status) == expected_scan_status


def test_scan_status_for_is_pure_projection():
    before = "running"
    result = scan_status_for(before)
    assert scan_status_for(before) == result
