from __future__ import annotations

import logging

import httpx
import pytest
from api.core.config import Settings, get_settings
from api.services.mailer import (
    NullMailer,
    ResendMailer,
    get_mailer,
    invite_link,
    reset_link,
)

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


def _configured(settings: Settings, **overrides: object) -> Settings:
    from pydantic import SecretStr

    return settings.model_copy(
        update={"resend_api_key": SecretStr("re_test_key"), **overrides}
    )


def _transport(monkeypatch: pytest.MonkeyPatch, handler: object) -> list[httpx.Request]:
    captured: list[httpx.Request] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)  # type: ignore[operator]

    real_client = httpx.Client

    def _client(**kwargs: object) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(_handle), **kwargs)

    monkeypatch.setattr("api.services.mailer.httpx.Client", _client)
    return captured


def test_invite_link_uses_documented_route() -> None:
    assert invite_link(TOKEN) == f"https://dmitri.peirce.dev/invite/{TOKEN}"


def test_reset_link_uses_documented_route() -> None:
    assert reset_link(TOKEN) == f"https://dmitri.peirce.dev/reset-password?token={TOKEN}"


def test_get_mailer_returns_null_mailer_without_api_key() -> None:
    assert isinstance(get_mailer(), NullMailer)


def test_get_mailer_returns_resend_mailer_with_api_key(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    configured = _configured(_mail_settings)
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)

    assert isinstance(get_mailer(), ResendMailer)


def test_get_mailer_treats_blank_api_key_as_unconfigured(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    from pydantic import SecretStr

    blank = _mail_settings.model_copy(update={"resend_api_key": SecretStr("")})
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: blank)

    assert isinstance(get_mailer(), NullMailer)


def test_resend_mailer_omits_blank_reply_to(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    configured = _configured(_mail_settings, mail_reply_to="")
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)
    captured = _transport(
        monkeypatch, lambda request: httpx.Response(200, json={"id": "1"})
    )

    ResendMailer().send_invite_link("user@example.com", TOKEN)

    import json

    assert "reply_to" not in json.loads(captured[0].content)


def test_null_mailer_never_logs_the_token(caplog: pytest.LogCaptureFixture) -> None:
    mailer = NullMailer()

    with caplog.at_level(logging.DEBUG):
        mailer.send_invite_link("user@example.com", TOKEN)
        mailer.send_reset_link("user@example.com", TOKEN)

    assert caplog.records
    assert TOKEN not in caplog.text


def test_resend_mailer_posts_plain_text_invite(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    configured = _configured(_mail_settings)
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)
    captured = _transport(
        monkeypatch, lambda request: httpx.Response(200, json={"id": "1"})
    )

    ResendMailer().send_invite_link("user@example.com", TOKEN)

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer re_test_key"

    import json

    payload = json.loads(request.content)
    assert payload["from"] == "Dmitri <no-reply@mail.peirce.dev>"
    assert payload["to"] == ["user@example.com"]
    assert "html" not in payload
    assert f"https://dmitri.peirce.dev/invite/{TOKEN}" in payload["text"]


def test_resend_mailer_posts_reset_link(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    configured = _configured(_mail_settings)
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)
    captured = _transport(
        monkeypatch, lambda request: httpx.Response(200, json={"id": "1"})
    )

    ResendMailer().send_reset_link("user@example.com", TOKEN)

    import json

    payload = json.loads(captured[0].content)
    assert f"https://dmitri.peirce.dev/reset-password?token={TOKEN}" in payload["text"]


def test_resend_mailer_includes_reply_to_when_configured(
    monkeypatch: pytest.MonkeyPatch, _mail_settings: Settings
) -> None:
    configured = _configured(_mail_settings, mail_reply_to="support@peirce.dev")
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)
    captured = _transport(
        monkeypatch, lambda request: httpx.Response(200, json={"id": "1"})
    )

    ResendMailer().send_invite_link("user@example.com", TOKEN)

    import json

    assert json.loads(captured[0].content)["reply_to"] == "support@peirce.dev"


def test_resend_mailer_swallows_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    _mail_settings: Settings,
) -> None:
    configured = _configured(_mail_settings)
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)

    def _boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("provider down", request=request)

    _transport(monkeypatch, _boom)

    with caplog.at_level(logging.DEBUG):
        result = ResendMailer().send_invite_link("user@example.com", TOKEN)

    assert result is None
    assert "failed" in caplog.text
    assert TOKEN not in caplog.text


def test_resend_mailer_swallows_provider_rejection(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    _mail_settings: Settings,
) -> None:
    configured = _configured(_mail_settings)
    monkeypatch.setattr("api.services.mailer.get_settings", lambda: configured)
    _transport(
        monkeypatch,
        lambda request: httpx.Response(422, json={"message": "invalid from"}),
    )

    with caplog.at_level(logging.DEBUG):
        result = ResendMailer().send_reset_link("user@example.com", TOKEN)

    assert result is None
    assert "422" in caplog.text
    assert TOKEN not in caplog.text
