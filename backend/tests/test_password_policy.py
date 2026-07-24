from __future__ import annotations

import hashlib

import httpx
import pytest
from api.core.config import get_settings
from api.services import passwords as passwords_module
from api.services.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_policy,
    verify_password,
)

VALID_PASSWORD = "Xk9$mQvL2pTz"


@pytest.fixture(autouse=True)
def _disable_hibp(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("HIBP_ENABLED", "false")
    yield
    get_settings.cache_clear()


def test_hash_and_verify_round_trip() -> None:
    hashed = hash_password(VALID_PASSWORD)
    assert hashed != VALID_PASSWORD
    assert verify_password(VALID_PASSWORD, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_valid_password_passes() -> None:
    validate_policy(VALID_PASSWORD, email=None, name=None, org_name=None)


@pytest.mark.parametrize(
    ("password", "kwargs"),
    [
        ("Sh0rt$abc", {}),
        ("password123", {}),
        ("Aaaaaa1$xyz9", {}),
        ("Xk9mQvLqwerty", {}),
        ("Xk9mQv12345678", {}),
        ("bob@example.com9$Zk", {"email": "bob@example.com"}),
        ("BobSmith9$Zpqrmn", {"name": "Bob Smith"}),
        ("Acmecorp9$Zpqrmn", {"org_name": "AcmeCorp"}),
    ],
)
def test_policy_rejects(password: str, kwargs: dict[str, str]) -> None:
    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_policy(password, **kwargs)
    assert exc_info.value.violations


def test_hibp_rejects_known_breached_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIBP_ENABLED", "true")
    get_settings.cache_clear()
    breached_password = "correcthorsebatterystaple"
    sha1 = hashlib.sha1(breached_password.encode("utf-8")).hexdigest().upper()
    suffix = sha1[5:]

    class FakeResponse:
        text = f"{suffix}:5\nAAAAA0AAAAAAAAAAAAAAAAAAAAAAAAAAAAA:1\n"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(passwords_module.httpx, "Client", FakeClient)

    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_policy(breached_password)
    assert any("breach" in v for v in exc_info.value.violations)


def test_hibp_skipped_not_failed_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIBP_ENABLED", "true")
    get_settings.cache_clear()

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(passwords_module.httpx, "Client", FakeClient)

    validate_policy(VALID_PASSWORD)
