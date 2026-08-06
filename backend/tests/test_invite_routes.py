from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from http.cookies import SimpleCookie
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.dependencies.auth import require_admin, require_user, require_user_row
from api.main import app
from api.models.identity import Invite, Org, User
from api.models.persistence import utc_now
from api.services.passwords import hash_password
from api.services.tokens import decode_access_token, hash_token
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_auth_wiring import _flatten_routes

VALID_PASSWORD = "Xk9$mQvL2pTz"


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


def _seed_invite(
    session: Session,
    *,
    org_id: UUID,
    email: str = "invitee@corp.com",
    role: str = "viewer",
    expires_delta: timedelta = timedelta(hours=1),
    consumed: bool = False,
) -> tuple[str, Invite]:
    raw = "test-invite-token"
    invite = Invite(
        org_id=org_id,
        email=email,
        role=role,
        token_hash=hash_token(raw),
        expires_at=utc_now() + expires_delta,
        consumed_at=utc_now() if consumed else None,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return raw, invite


def test_admin_creates_invite_returns_201_exact_shape(
    client: TestClient, administrative_session: Session, seeded_org: Org, bearer_headers
) -> None:
    response = client.post(
        "/api/v1/invites",
        json={"email": "new@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    assert set(response.json().keys()) == {"invite_token", "expires_at"}


def test_admin_creates_invite_emails_a_working_invite_link(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
    sent_emails,
) -> None:
    captured = sent_emails()

    response = client.post(
        "/api/v1/invites",
        json={"email": "new@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    assert len(captured) == 1

    payload = json.loads(captured[0].content)
    assert payload["to"] == ["new@corp.com"]

    token = response.json()["invite_token"]
    assert f"/invite?token={token}" in payload["text"]

    accepted = client.post(
        "/api/v1/invites/accept",
        json={"token": token, "password": VALID_PASSWORD},
    )
    assert accepted.status_code == 201


def test_create_invite_survives_a_downed_provider(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
    sent_emails,
) -> None:
    sent_emails(fail=True)

    response = client.post(
        "/api/v1/invites",
        json={"email": "new@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    token = response.json()["invite_token"]

    invite = administrative_session.exec(select(Invite)).one()
    assert invite.token_hash == hash_token(token)


def test_viewer_cannot_create_invite_and_no_invite_persists(
    client: TestClient, administrative_session: Session, seeded_org: Org, bearer_headers
) -> None:
    response = client.post(
        "/api/v1/invites",
        json={"email": "new@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 403
    assert administrative_session.exec(select(Invite)).first() is None


def test_create_invite_without_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/invites", json={"email": "new@corp.com", "role": "viewer"}
    )

    assert response.status_code == 401


def test_create_invite_for_existing_member_returns_400(
    client: TestClient, administrative_session: Session, seeded_org: Org, bearer_headers
) -> None:
    user = User(
        org_id=seeded_org.id,
        email="already@corp.com",
        password_hash=hash_password(VALID_PASSWORD),
        role="viewer",
    )
    administrative_session.add(user)
    administrative_session.commit()

    response = client.post(
        "/api/v1/invites",
        json={"email": "already@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "email_already_member"
    assert administrative_session.exec(select(Invite)).first() is None


def test_create_invite_for_live_address_returns_409_invite_already_pending(
    client: TestClient, administrative_session: Session, seeded_org: Org, bearer_headers
) -> None:
    first = client.post(
        "/api/v1/invites",
        json={"email": "pending@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/invites",
        json={"email": "pending@corp.com", "role": "admin"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "invite_already_pending"
    rows = administrative_session.exec(select(Invite)).all()
    assert len(rows) == 1


def test_create_invite_member_and_pending_precedence_returns_400_member(
    client: TestClient, administrative_session: Session, seeded_org: Org, bearer_headers
) -> None:
    user = User(
        org_id=seeded_org.id,
        email="both@corp.com",
        password_hash=hash_password(VALID_PASSWORD),
        role="viewer",
    )
    administrative_session.add(user)
    administrative_session.commit()
    _seed_invite(administrative_session, org_id=seeded_org.id, email="both@corp.com")

    response = client.post(
        "/api/v1/invites",
        json={"email": "both@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "email_already_member"


def test_create_invite_for_another_orgs_user_returns_201_like_fresh_address(
    client: TestClient, administrative_session: Session, seeded_org: Org, bearer_headers
) -> None:
    other_org = Org(name="Other Org")
    administrative_session.add(other_org)
    administrative_session.commit()
    administrative_session.refresh(other_org)
    other_user = User(
        org_id=other_org.id,
        email="elsewhere@corp.com",
        password_hash=hash_password(VALID_PASSWORD),
        role="viewer",
    )
    administrative_session.add(other_user)
    administrative_session.commit()

    response = client.post(
        "/api/v1/invites",
        json={"email": "elsewhere@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    assert set(response.json().keys()) == {"invite_token", "expires_at"}


def test_create_invite_org_id_in_body_returns_422(
    client: TestClient, seeded_org: Org, bearer_headers
) -> None:
    response = client.post(
        "/api/v1/invites",
        json={"email": "new@corp.com", "role": "viewer", "org_id": str(uuid4())},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422


def test_accept_invite_returns_login_response_and_refresh_cookie(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert response.cookies.get("dmitri_refresh")


def test_accepted_invite_token_works_against_protected_read_route(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    accept_response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )
    access_token = accept_response.json()["access_token"]

    created_user = administrative_session.exec(select(User)).one()
    assert created_user.email == invite.email
    assert created_user.role == invite.role
    assert created_user.org_id == invite.org_id
    claims = decode_access_token(access_token)
    assert claims["sub"] == str(created_user.id)
    assert claims["org_id"] == str(seeded_org.id)
    assert claims["role"] == invite.role

    hosts_response = client.get(
        "/api/v1/hosts", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert hosts_response.status_code == 200


def test_second_accept_returns_410_and_only_one_user(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    first = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )

    assert second.status_code == 410
    assert second.json()["error"]["code"] == "invalid_invite_token"
    assert administrative_session.exec(select(User)).one()


def test_accept_expired_invite_returns_410(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(
        administrative_session, org_id=seeded_org.id, expires_delta=timedelta(hours=-1)
    )

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_invite_token"


def test_accept_unknown_token_returns_410(client: TestClient) -> None:
    response = client.post(
        "/api/v1/invites/accept",
        json={"token": "does-not-exist", "password": VALID_PASSWORD},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_invite_token"


def test_accept_dead_token_beats_weak_password(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(
        administrative_session, org_id=seeded_org.id, consumed=True
    )

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": "aaabbbcccddd"},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_invite_token"


def test_accept_with_email_in_body_returns_422(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "email": invite.email, "password": VALID_PASSWORD},
    )

    assert response.status_code == 422
    assert administrative_session.exec(select(User)).first() is None


def test_accept_already_registered_in_another_org_returns_400_email_already_registered(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)
    other_org = Org(name="Other Org")
    administrative_session.add(other_org)
    administrative_session.commit()
    administrative_session.refresh(other_org)
    administrative_session.add(
        User(
            org_id=other_org.id,
            email=invite.email,
            password_hash=hash_password(VALID_PASSWORD),
            role="viewer",
        )
    )
    administrative_session.commit()

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "email_already_registered"


def test_accept_weak_password_returns_400_and_no_user_created(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": "aaabbbcccddd"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "password_policy_violation"
    assert administrative_session.exec(select(User)).first() is None
    administrative_session.refresh(invite)
    assert invite.consumed_at is None


def test_accept_breached_password_returns_400_and_no_user_created(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.core.config import get_settings
    from api.services import passwords as passwords_module

    monkeypatch.setenv("HIBP_ENABLED", "true")
    get_settings.cache_clear()

    breached_password = "correcthorsebatterystaple"
    sha1 = hashlib.sha1(breached_password.encode("utf-8")).hexdigest().upper()
    suffix = sha1[5:]

    class FakeResponse:
        text = f"{suffix}:5\n"

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

    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": breached_password},
    )

    assert response.status_code == 400
    assert administrative_session.exec(select(User)).first() is None
    administrative_session.refresh(invite)
    assert invite.consumed_at is None


def test_old_path_carried_token_route_is_gone(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post(
        f"/api/v1/invites/{raw}/accept",
        json={"email": invite.email, "password": VALID_PASSWORD},
    )

    assert response.status_code == 404


def test_lookup_live_invite_returns_200_with_email_role_and_org_name(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post("/api/v1/invites/lookup", json={"token": raw})

    assert response.status_code == 200
    assert response.json() == {
        "email": invite.email,
        "role": invite.role,
        "org_name": seeded_org.name,
    }


def test_lookup_without_credentials_succeeds(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, _invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    client.cookies.clear()
    response = client.post("/api/v1/invites/lookup", json={"token": raw})

    assert response.status_code == 200
    route = next(
        r
        for r in _flatten_routes(app.routes)
        if getattr(r, "path", None) == "/api/v1/invites/lookup"
        and "POST" in getattr(r, "methods", set())
    )
    calls = {dep.call for dep in route.dependant.dependencies}

    assert require_user not in calls
    assert require_admin not in calls
    assert require_user_row not in calls


def test_lookup_twice_returns_identical_bodies(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    first = client.post("/api/v1/invites/lookup", json={"token": raw})
    second = client.post("/api/v1/invites/lookup", json={"token": raw})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    administrative_session.refresh(invite)
    assert invite.consumed_at is None


def test_lookup_then_accept_still_returns_201(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    for _ in range(3):
        looked_up = client.post("/api/v1/invites/lookup", json={"token": raw})
        assert looked_up.status_code == 200

    response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )

    assert response.status_code == 201
    assert response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"
    assert response.cookies.get("dmitri_refresh")


@pytest.mark.parametrize(
    "consumed,expires_delta",
    [(True, timedelta(hours=1)), (False, timedelta(hours=-1))],
)
def test_lookup_dead_invite_returns_410(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    consumed: bool,
    expires_delta: timedelta,
) -> None:
    raw, _invite = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        consumed=consumed,
        expires_delta=expires_delta,
    )

    response = client.post("/api/v1/invites/lookup", json={"token": raw})

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_invite_token"


def test_lookup_unknown_token_returns_410(client: TestClient) -> None:
    response = client.post("/api/v1/invites/lookup", json={"token": "does-not-exist"})

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "invalid_invite_token"


def test_lookup_expired_and_forged_tokens_are_byte_identical(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, _invite = _seed_invite(
        administrative_session, org_id=seeded_org.id, expires_delta=timedelta(hours=-1)
    )

    expired = client.post("/api/v1/invites/lookup", json={"token": raw})
    forged = client.post("/api/v1/invites/lookup", json={"token": "fabricated-token"})

    assert expired.status_code == forged.status_code
    assert expired.json() == forged.json()


def test_lookup_gone_body_matches_accept_route_gone_body(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, invite = _seed_invite(
        administrative_session, org_id=seeded_org.id, expires_delta=timedelta(hours=-1)
    )

    lookup = client.post("/api/v1/invites/lookup", json={"token": raw})
    accept = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )

    assert lookup.status_code == accept.status_code == 410
    assert lookup.json() == accept.json()


def test_lookup_rejects_unknown_body_fields(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    raw, _invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    response = client.post(
        "/api/v1/invites/lookup", json={"token": raw, "role": "admin"}
    )

    assert response.status_code == 422


def test_accept_invite_refresh_cookie_matches_login_route_cookie_policy(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    """The invite-accept route must reuse the shared session/cookie helper
    rather than hand-roll its own LoginResponse/cookie: its Set-Cookie
    name/path/flags must match what the auth login route sets. Asserted on
    observable HTTP behavior, not on the helper's name or module, so it
    survives login_response moving to a shared module."""
    raw, invite = _seed_invite(administrative_session, org_id=seeded_org.id)

    accept_response = client.post(
        "/api/v1/invites/accept",
        json={"token": raw, "password": VALID_PASSWORD},
    )
    assert accept_response.status_code == 201
    assert accept_response.json()["access_token"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": invite.email, "password": VALID_PASSWORD},
    )
    assert login_response.status_code == 200

    def _refresh_cookie_attrs(response) -> dict[str, object]:
        set_cookie_headers = response.headers.get_list("set-cookie")
        header = next(
            h for h in set_cookie_headers if h.startswith("dmitri_refresh=")
        )
        cookie: SimpleCookie = SimpleCookie()
        cookie.load(header)
        morsel = cookie["dmitri_refresh"]
        return {
            "path": morsel["path"],
            "httponly": bool(morsel["httponly"]),
            "samesite": morsel["samesite"],
            "secure": bool(morsel["secure"]),
        }

    assert _refresh_cookie_attrs(accept_response) == _refresh_cookie_attrs(
        login_response
    )
