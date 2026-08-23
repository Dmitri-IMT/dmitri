from __future__ import annotations

import json
import logging
import re

import pytest
from api.core.config import Settings, get_settings
from api.services.mailer import (
    INVITE_BODY,
    INVITE_BODY_HTML,
    RESET_BODY,
    RESET_BODY_HTML,
    BackgroundMailer,
    NullMailer,
    ResendMailer,
    get_mailer,
    invite_link,
    reset_link,
)
from fastapi import BackgroundTasks
from pydantic import SecretStr

TOKEN = "tok_abc123_secret"


@pytest.fixture(autouse=True)
def _mail_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = get_settings().model_copy(
        update={
            "resend_api_key": None,
            "app_base_url": "https://dmitri.peirce.dev",
            "mail_from": "Dmitri <no-reply@mail.peirce.dev>",
            "mail_reply_to": None,
        }
    )
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: settings)
    return settings


def test_invite_link_uses_documented_route() -> None:
    assert invite_link(TOKEN) == f"https://dmitri.peirce.dev/invite?token={TOKEN}"


def test_reset_link_uses_documented_route() -> None:
    assert reset_link(TOKEN) == f"https://dmitri.peirce.dev/reset-password?token={TOKEN}"


def test_get_mailer_returns_null_mailer_without_api_key() -> None:
    assert isinstance(get_mailer(BackgroundTasks()), NullMailer)


def test_get_mailer_returns_backgrounded_resend_mailer_with_api_key(
    sent_emails,
) -> None:
    sent_emails()

    mailer = get_mailer(BackgroundTasks())

    assert isinstance(mailer, BackgroundMailer)
    assert isinstance(mailer.mailer, ResendMailer)


def test_get_mailer_treats_blank_api_key_as_unconfigured(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    blank = _mail_settings.model_copy(update={"resend_api_key": SecretStr("")})
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: blank)

    assert isinstance(get_mailer(BackgroundTasks()), NullMailer)


def test_background_mailer_defers_the_send_until_the_response_is_out(
    sent_emails,
) -> None:
    captured = sent_emails()
    tasks = BackgroundTasks()

    get_mailer(tasks).send_invite_link("user@example.com", TOKEN)

    # Nothing has left the process yet -- the request is free to return.
    assert captured == []
    assert len(tasks.tasks) == 1

    tasks.tasks[0].func(*tasks.tasks[0].args)

    assert len(captured) == 1


def test_resend_mailer_omits_blank_reply_to(sent_emails) -> None:
    captured = sent_emails(mail_reply_to="")

    ResendMailer().send_invite_link("user@example.com", TOKEN)

    assert "reply_to" not in json.loads(captured[0].content)


def test_null_mailer_never_logs_the_token(caplog: pytest.LogCaptureFixture) -> None:
    mailer = NullMailer()

    with caplog.at_level(logging.DEBUG):
        mailer.send_invite_link("user@example.com", TOKEN)
        mailer.send_reset_link("user@example.com", TOKEN)

    assert caplog.records
    assert TOKEN not in caplog.text


def test_resend_mailer_posts_multipart_invite(sent_emails) -> None:
    captured = sent_emails()

    mailer = ResendMailer()
    mailer.send_invite_link("user@example.com", TOKEN)

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer re_test_key"

    payload = json.loads(request.content)
    assert payload["from"] == "Dmitri <no-reply@mail.peirce.dev>"
    assert payload["to"] == ["user@example.com"]
    link = f"https://dmitri.peirce.dev/invite?token={TOKEN}"
    ttl = mailer.invite_ttl_hours
    assert payload["text"] == INVITE_BODY.format(link=link, ttl_hours=ttl)
    assert payload["html"] == INVITE_BODY_HTML.format(link=link, ttl_hours=ttl)
    assert f'<a href="{link}">{link}</a>' in payload["html"]


@pytest.mark.parametrize(
    ("send", "link"),
    [
        ("send_invite_link", f"https://dmitri.peirce.dev/invite?token={TOKEN}"),
        (
            "send_reset_link",
            f"https://dmitri.peirce.dev/reset-password?token={TOKEN}",
        ),
    ],
)
def test_html_carries_no_markup_that_reads_as_marketing(
    sent_emails, send: str, link: str
) -> None:
    captured = sent_emails()

    getattr(ResendMailer(), send)("user@example.com", TOKEN)

    payload = json.loads(captured[0].content)
    html = payload["html"]
    assert "<img" not in html
    assert "<table" not in html
    assert "<link" not in html
    assert set(re.findall(r"https?://[^\"\s<]+", html)) == {link}
    assert "<" not in payload["text"]


def test_resend_mailer_posts_reset_link(sent_emails) -> None:
    captured = sent_emails()

    mailer = ResendMailer()
    mailer.send_reset_link("user@example.com", TOKEN)

    payload = json.loads(captured[0].content)
    link = f"https://dmitri.peirce.dev/reset-password?token={TOKEN}"
    ttl = mailer.reset_ttl_minutes
    assert payload["text"] == RESET_BODY.format(link=link, ttl_minutes=ttl)
    assert payload["html"] == RESET_BODY_HTML.format(link=link, ttl_minutes=ttl)


def test_resend_mailer_never_logs_the_token_on_the_success_path(
    caplog: pytest.LogCaptureFixture, sent_emails
) -> None:
    sent_emails()

    with caplog.at_level(logging.DEBUG):
        ResendMailer().send_invite_link("user@example.com", TOKEN)
        ResendMailer().send_reset_link("user@example.com", TOKEN)

    assert TOKEN not in caplog.text


def test_resend_mailer_includes_reply_to_when_configured(sent_emails) -> None:
    captured = sent_emails(mail_reply_to="support@peirce.dev")

    ResendMailer().send_invite_link("user@example.com", TOKEN)

    assert json.loads(captured[0].content)["reply_to"] == "support@peirce.dev"


def test_resend_mailer_swallows_transport_failure(
    caplog: pytest.LogCaptureFixture, sent_emails
) -> None:
    sent_emails(fail=True)

    with caplog.at_level(logging.DEBUG):
        result = ResendMailer().send_invite_link("user@example.com", TOKEN)

    assert result is None
    assert "failed" in caplog.text
    assert TOKEN not in caplog.text


def test_resend_mailer_swallows_provider_rejection(
    caplog: pytest.LogCaptureFixture, sent_emails
) -> None:
    sent_emails(status=422)

    with caplog.at_level(logging.DEBUG):
        result = ResendMailer().send_reset_link("user@example.com", TOKEN)

    assert result is None
    assert "422" in caplog.text
    assert TOKEN not in caplog.text
