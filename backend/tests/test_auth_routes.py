from __future__ import annotations

from datetime import timedelta

import pytest
from api.db.session import get_session
from api.main import app
from api.models.identity import Org, User
from api.models.persistence import utc_now
from api.models.session import PasswordResetToken, RefreshToken
from api.services.auth import forgot_password
from api.services.mailer import NullMailer
from api.services.passwords import hash_password, verify_password
from fastapi.testclient import TestClient
from sqlmodel import Session, select

VALID_PASSWORD = "Xk9$mQvL2pTz"
OTHER_VALID_PASSWORD = "Zp4#nWxR7bHq"
COOKIE_NAME = "dmitri_refresh"


@pytest.fixture(autouse=True)
def _disable_hibp(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("HIBP_ENABLED", "false")
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_user(session: Session, *, password: str = VALID_PASSWORD) -> User:
    org = Org(name="Acme")
    session.add(org)
    session.commit()
    session.refresh(org)
    user = User(
        org_id=org.id,
        email="alice@corp.com",
        password_hash=hash_password(password),
        role="admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_login_issues_access_token_and_refresh_cookie(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert response.cookies.get(COOKIE_NAME)


def test_login_bad_credentials_returns_401_no_tokens(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": "wrong-pass"},
    )

    assert response.status_code == 401
    assert COOKIE_NAME not in response.cookies


def test_refresh_rotates_and_kills_old_token(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )
    old_refresh = login_response.cookies.get(COOKIE_NAME)

    refresh_response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: old_refresh}
    )
    assert refresh_response.status_code == 200
    new_refresh = refresh_response.cookies.get(COOKIE_NAME)
    assert new_refresh
    assert new_refresh != old_refresh

    replay_response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: old_refresh}
    )
    assert replay_response.status_code == 401


def test_refresh_reuse_revokes_the_whole_family(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )
    old_refresh = login_response.cookies.get(COOKIE_NAME)

    rotate_response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: old_refresh}
    )
    new_refresh = rotate_response.cookies.get(COOKIE_NAME)

    reuse_response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: old_refresh}
    )
    assert reuse_response.status_code == 401

    second_family_response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: new_refresh}
    )
    assert second_family_response.status_code == 401


def test_logout_revokes_current_family(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )
    refresh_token = login_response.cookies.get(COOKIE_NAME)

    logout_response = client.post(
        "/api/v1/auth/logout", cookies={COOKIE_NAME: refresh_token}
    )
    assert logout_response.status_code == 204

    replay_response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: refresh_token}
    )
    assert replay_response.status_code == 401


def test_refresh_past_fixed_7day_window_is_rejected(
    client: TestClient, administrative_session: Session
) -> None:
    user = _seed_user(administrative_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )
    refresh_token = login_response.cookies.get(COOKIE_NAME)

    row = administrative_session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    ).one()
    row.family_expires_at = utc_now() - timedelta(days=1)
    administrative_session.add(row)
    administrative_session.commit()

    response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: refresh_token}
    )
    assert response.status_code == 401


def _login_and_get_access_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )
    return response.json()["access_token"]


def test_change_password_wrong_current_returns_400_not_401(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    access_token = _login_and_get_access_token(client)

    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong-pass", "new_password": OTHER_VALID_PASSWORD},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    assert response.status_code != 401
    assert response.json()["error"]["code"] == "wrong_current_password"


def test_change_password_weak_new_password_returns_400(
    client: TestClient, administrative_session: Session
) -> None:
    user = _seed_user(administrative_session)
    access_token = _login_and_get_access_token(client)

    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": VALID_PASSWORD, "new_password": "aaabbbcccddd"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    assert response.status_code != 401
    assert response.json()["error"]["code"] == "password_policy_violation"
    administrative_session.refresh(user)
    assert verify_password(VALID_PASSWORD, user.password_hash)


def test_forgot_password_returns_204_for_real_and_fake_email(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)

    real_response = client.post(
        "/api/v1/auth/forgot-password", json={"email": "alice@corp.com"}
    )
    fake_response = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@corp.com"}
    )

    assert real_response.status_code == 204
    assert fake_response.status_code == 204


def test_forgot_password_sends_nothing_for_an_unknown_email(
    client: TestClient, administrative_session: Session, sent_emails
) -> None:
    _seed_user(administrative_session)
    captured = sent_emails()

    unknown = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@corp.com"}
    )

    assert unknown.status_code == 204
    assert captured == []

    known = client.post(
        "/api/v1/auth/forgot-password", json={"email": "alice@corp.com"}
    )

    # Same status, same empty body. The send is a background task, so it also
    # lands after the response and cannot be timed: one email left the
    # building, the other did not, and the caller cannot tell which.
    assert known.status_code == unknown.status_code
    assert known.content == unknown.content
    assert len(captured) == 1


class _CapturingResetMailer(NullMailer):
    def __init__(self) -> None:
        self.token: str | None = None

    def send_reset_link(self, email: str, token: str) -> None:
        self.token = token


def _request_reset(session: Session, mailer: _CapturingResetMailer) -> None:
    forgot_password(session, email="alice@corp.com", mailer=mailer)


def test_reset_password_consumes_token_once(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    mailer = _CapturingResetMailer()
    _request_reset(administrative_session, mailer)

    first_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": OTHER_VALID_PASSWORD},
    )
    assert first_response.status_code == 204

    second_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": VALID_PASSWORD},
    )
    assert second_response.status_code == 410
    assert second_response.json()["error"]["code"] == "invalid_reset_token"


def test_reset_password_unknown_token_returns_410(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "never-issued", "new_password": OTHER_VALID_PASSWORD},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_reset_token"


def test_reset_password_expired_token_returns_410(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    mailer = _CapturingResetMailer()
    _request_reset(administrative_session, mailer)

    row = administrative_session.exec(select(PasswordResetToken)).one()
    row.expires_at = utc_now() - timedelta(minutes=1)
    administrative_session.add(row)
    administrative_session.commit()

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": OTHER_VALID_PASSWORD},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_reset_token"


def test_reset_password_weak_password_returns_400(
    client: TestClient, administrative_session: Session
) -> None:
    user = _seed_user(administrative_session)
    mailer = _CapturingResetMailer()
    _request_reset(administrative_session, mailer)

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": "aaabbbcccddd"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "password_policy_violation"
    administrative_session.refresh(user)
    assert verify_password(VALID_PASSWORD, user.password_hash)

    retry_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": OTHER_VALID_PASSWORD},
    )
    assert retry_response.status_code == 204


def test_reset_password_dead_token_beats_weak_password(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    mailer = _CapturingResetMailer()
    _request_reset(administrative_session, mailer)

    client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": OTHER_VALID_PASSWORD},
    )

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": "aaabbbcccddd"},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_reset_token"


def test_reset_password_revokes_all_refresh_families(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@corp.com", "password": VALID_PASSWORD},
    )
    old_refresh = login_response.cookies.get(COOKIE_NAME)

    mailer = _CapturingResetMailer()
    _request_reset(administrative_session, mailer)
    client.post(
        "/api/v1/auth/reset-password",
        json={"token": mailer.token, "new_password": OTHER_VALID_PASSWORD},
    )

    response = client.post(
        "/api/v1/auth/refresh", cookies={COOKIE_NAME: old_refresh}
    )
    assert response.status_code == 401
