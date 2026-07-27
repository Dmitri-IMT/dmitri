from __future__ import annotations

import logging

import pytest
from api.services.mailer import LogMailer


def test_log_mailer_logs_reset_link(caplog: pytest.LogCaptureFixture) -> None:
    mailer = LogMailer()

    with caplog.at_level(logging.INFO):
        result = mailer.send_reset_link("user@example.com", "tok_abc123")

    assert result is None
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "user@example.com" in message
    assert "tok_abc123" in message


def test_log_mailer_logs_invite_link(caplog: pytest.LogCaptureFixture) -> None:
    mailer = LogMailer()

    with caplog.at_level(logging.INFO):
        result = mailer.send_invite_link("user@example.com", "tok_xyz789")

    assert result is None
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "user@example.com" in message
    assert "tok_xyz789" in message
