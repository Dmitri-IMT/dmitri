"""Service layer placeholder."""
from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    def send_reset_link(self, email: str, token: str) -> None: ...
    def send_invite_link(self, email: str, token: str) -> None: ...


class LogMailer:
    def send_reset_link(self, email: str, token: str) -> None:
        logger.info("password reset link for %s: token=%s", email, token)

    def send_invite_link(self, email: str, token: str) -> None:
        logger.info("invite link for %s: token=%s", email, token)
