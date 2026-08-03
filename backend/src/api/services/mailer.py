from __future__ import annotations

import logging
from typing import Protocol

import httpx
from fastapi import BackgroundTasks

from api.core.config import get_settings

logger = logging.getLogger(__name__)

INVITE_SUBJECT = "You have been invited to Dmitri"
RESET_SUBJECT = "Reset your Dmitri password"

INVITE_BODY = """You have been invited to join an organisation on Dmitri.

Open the link below to create your account:

{link}

This link can only be used once and expires in {ttl_hours} hours.

If you were not expecting this invitation, you can ignore this email.
"""

RESET_BODY = """We received a request to reset the password for this Dmitri account.

Open the link below to choose a new password:

{link}

This link can only be used once and expires in {ttl_minutes} minutes.

If you did not request a password reset, you can ignore this email. Your
password will not change until you use the link above.
"""


class Mailer(Protocol):
    def send_reset_link(self, email: str, token: str) -> None: ...
    def send_invite_link(self, email: str, token: str) -> None: ...


def invite_link(token: str) -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/invite?token={token}"


def reset_link(token: str) -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/reset-password?token={token}"


class NullMailer:
    def send_reset_link(self, email: str, token: str) -> None:
        self._skip("password reset", email)

    def send_invite_link(self, email: str, token: str) -> None:
        self._skip("invite", email)

    def _skip(self, kind: str, email: str) -> None:
        logger.warning(
            "RESEND_API_KEY is not set; %s email to %s was not sent", kind, email
        )


class ResendMailer:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.resend_api_key.get_secret_value()
        self.base_url = settings.resend_api_base_url
        self.sender = settings.mail_from
        self.reply_to = settings.mail_reply_to
        self.timeout = settings.mail_timeout_seconds
        self.invite_ttl_hours = settings.invite_ttl_hours
        self.reset_ttl_minutes = settings.reset_token_ttl_minutes

    def send_invite_link(self, email: str, token: str) -> None:
        self._send(
            email,
            INVITE_SUBJECT,
            INVITE_BODY.format(
                link=invite_link(token), ttl_hours=self.invite_ttl_hours
            ),
            "invite",
        )

    def send_reset_link(self, email: str, token: str) -> None:
        self._send(
            email,
            RESET_SUBJECT,
            RESET_BODY.format(
                link=reset_link(token), ttl_minutes=self.reset_ttl_minutes
            ),
            "password reset",
        )

    def _send(self, email: str, subject: str, body: str, kind: str) -> None:
        payload: dict[str, object] = {
            "from": self.sender,
            "to": [email],
            "subject": subject,
            "text": body,
        }
        if self.reply_to:
            payload["reply_to"] = self.reply_to

        # A provider outage must not fail the caller: the invite is already
        # committed and its token still returned to the admin. Nothing logged
        # on these paths may include the token.
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            logger.error("%s email to %s failed: %s", kind, email, type(exc).__name__)
            return

        if response.status_code >= 400:
            logger.error(
                "%s email to %s rejected by provider with status %s",
                kind,
                email,
                response.status_code,
            )


class BackgroundMailer:
    """Runs the provider call after the response has been sent.

    Two reasons, both about the request and not about the email: the request's
    database session is released before background tasks run, so a slow
    provider no longer pins a pooled connection, and the response time of
    `forgot-password` stops depending on whether an email went out — otherwise
    latency alone tells an attacker which addresses exist.
    """

    def __init__(self, tasks: BackgroundTasks, mailer: Mailer) -> None:
        self.tasks = tasks
        self.mailer = mailer

    def send_invite_link(self, email: str, token: str) -> None:
        self.tasks.add_task(self.mailer.send_invite_link, email, token)

    def send_reset_link(self, email: str, token: str) -> None:
        self.tasks.add_task(self.mailer.send_reset_link, email, token)


def get_mailer(tasks: BackgroundTasks) -> Mailer:
    api_key = get_settings().resend_api_key
    if api_key is None or not api_key.get_secret_value():
        return NullMailer()
    return BackgroundMailer(tasks, ResendMailer())
