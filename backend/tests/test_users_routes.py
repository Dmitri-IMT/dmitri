from __future__ import annotations

from uuid import UUID

from api.models.identity import Org, User
from api.services.passwords import hash_password
from api.services.tokens import create_access_token
from sqlmodel import Session
from starlette.testclient import TestClient

VALID_PASSWORD = "Xk9$mQvL2pTz"


def _assert_error_envelope(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert "detail" not in body
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["details"] == {}


def _seed_user(session: Session, *, role: str, email: str = "alice@corp.com") -> User:
    org = Org(name="Org A")
    session.add(org)
    session.flush()
    user = User(
        org_id=org.id,
        email=email,
        password_hash=hash_password(VALID_PASSWORD),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _user_bearer_headers(user: User, *, role: str | None = None) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=role if role is not None else user.role,
    )
    return {"Authorization": f"Bearer {token}"}


def test_users_me_without_bearer_returns_401_envelope(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session, role="admin")
    response = client.get("/api/v1/users/me")
    _assert_error_envelope(response, 401, "unauthorized")


def test_users_me_with_garbage_bearer_returns_401_envelope(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_user(administrative_session, role="admin")
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    _assert_error_envelope(response, 401, "unauthorized")


def test_users_me_admin_returns_profile(
    client: TestClient, administrative_session: Session
) -> None:
    user = _seed_user(administrative_session, role="admin")
    response = client.get("/api/v1/users/me", headers=_user_bearer_headers(user))
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.id)
    assert body["email"] == user.email
    assert body["role"] == "admin"
    assert "password_expires_at" not in body


def test_users_me_viewer_returns_profile(
    client: TestClient, administrative_session: Session
) -> None:
    user = _seed_user(administrative_session, role="viewer", email="viewer@corp.com")
    response = client.get("/api/v1/users/me", headers=_user_bearer_headers(user))
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.id)
    assert body["email"] == user.email
    assert body["role"] == "viewer"
    assert "password_expires_at" not in body


def test_users_me_role_from_row_not_jwt(
    client: TestClient, administrative_session: Session
) -> None:
    user = _seed_user(administrative_session, role="viewer")
    response = client.get(
        "/api/v1/users/me",
        headers=_user_bearer_headers(user, role="admin"),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


def test_users_me_missing_user_row_returns_401_envelope(
    client: TestClient, administrative_session: Session
) -> None:
    org = Org(name="Org A")
    administrative_session.add(org)
    administrative_session.commit()
    administrative_session.refresh(org)
    token = create_access_token(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        org_id=org.id,
        role="admin",
    )
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    _assert_error_envelope(response, 401, "unauthorized")
