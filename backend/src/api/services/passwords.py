from __future__ import annotations

import hashlib
import re

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from api.core.config import get_settings

MIN_LENGTH = 12

_HASHER = PasswordHasher()

_COMMON_PASSWORDS = {
    "password", "password123", "123456", "12345678", "123456789",
    "qwerty123", "letmein123", "welcome123", "admin1234", "iloveyou1",
    "sunshine1", "princess1", "football1", "monkey123", "dragon123",
}

_KEYBOARD_SUFFIXES = ("qwerty", "asdf", "zxcv", "1qaz", "!qaz", "1!")

_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")
_REPEATED_NUMBER_RE = re.compile(
    r"(?:0123|1234|2345|3456|4567|5678|6789|9876|8765|7654|6543|5432|4321|3210)"
)


class PasswordPolicyError(ValueError):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(", ".join(violations))


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _contains_substring(password: str, candidate: str | None) -> bool:
    if not candidate:
        return False
    lowered = password.lower()
    for part in re.split(r"[@\s._-]+", candidate.lower()):
        if len(part) >= 3 and part in lowered:
            return True
    return False


def _check_hibp(password: str) -> bool:
    settings = get_settings()
    if not settings.hibp_enabled:
        return False
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        with httpx.Client(timeout=settings.hibp_timeout_seconds) as client:
            response = client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    for line in response.text.splitlines():
        line_suffix, _, _count = line.partition(":")
        if line_suffix.strip().upper() == suffix:
            return True
    return False


def validate_policy(
    password: str,
    *,
    email: str | None = None,
    name: str | None = None,
    org_name: str | None = None,
) -> None:
    violations: list[str] = []

    if len(password) < MIN_LENGTH:
        violations.append(f"must be at least {MIN_LENGTH} characters")

    if password.lower() in _COMMON_PASSWORDS:
        violations.append("must not be a common password")

    if _REPEATED_CHAR_RE.search(password):
        violations.append("must not contain repeated characters")

    if any(password.lower().endswith(suffix) for suffix in _KEYBOARD_SUFFIXES):
        violations.append("must not end with a keyboard pattern")

    if _REPEATED_NUMBER_RE.search(password):
        violations.append("must not contain a sequential number pattern")

    if _contains_substring(password, email):
        violations.append("must not contain your email")

    if _contains_substring(password, name):
        violations.append("must not contain your name")

    if _contains_substring(password, org_name):
        violations.append("must not contain your organization name")

    if _check_hibp(password):
        violations.append("must not be a known breached password")

    if violations:
        raise PasswordPolicyError(violations)
