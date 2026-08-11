from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.dependencies.auth import CallerIdentity, require_admin
from api.main import app
from api.models.identity import Org, User
from api.services import users
from api.services.passwords import hash_password
from api.services.tokens import create_access_token
from fastapi.testclient import TestClient
from sqlmodel import Session

VALID_PASSWORD = "Xk9$mQvL2pTz"
ALLOWED_ORIGIN = "http://localhost:5173"


def _assert_error_envelope(
    response,
    status_code: int,
    code: str,
    *,
    message: str | None = None,
    details: dict[str, str] | None = None,
) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert "detail" not in body
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["details"] == ({} if details is None else details)
    if message is not None:
        assert body["error"]["message"] == message


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_user(
    session: Session,
    *,
    org_id: UUID,
    email: str,
    role: str = "viewer",
    user_id: UUID | None = None,
    last_login_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> User:
    user = User(
        id=user_id or uuid4(),
        org_id=org_id,
        email=email,
        password_hash=hash_password(VALID_PASSWORD),
        role=role,
        last_login_at=last_login_at,
        last_seen_at=last_seen_at,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _headers(user: User, *, role: str | None = None) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=role if role is not None else user.role,
    )
    return {"Authorization": f"Bearer {token}"}


def test_admin_lists_only_org_members_with_exact_public_shape(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    seen_at = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    visible = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="seen@corp.com",
        role="admin",
        last_login_at=seen_at,
        last_seen_at=seen_at,
    )
    never_seen = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="new@corp.com",
    )
    other_org = Org(name="Other Org")
    administrative_session.add(other_org)
    administrative_session.commit()
    administrative_session.refresh(other_org)
    foreign = _seed_user(
        administrative_session,
        org_id=other_org.id,
        email="foreign@corp.com",
        last_login_at=seen_at,
        last_seen_at=seen_at,
    )

    response = client.get(
        "/api/v1/users", headers=bearer_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data"}
    assert {row["user_id"] for row in body["data"]} == {
        str(visible.id),
        str(never_seen.id),
    }
    assert str(foreign.id) not in response.text
    for row in body["data"]:
        assert set(row) == {"user_id", "email", "role", "last_seen_at"}
    assert "last_login_at" not in response.text
    assert "status" not in response.text
    serialized_never_seen = next(
        row for row in body["data"] if row["user_id"] == str(never_seen.id)
    )
    assert serialized_never_seen["last_seen_at"] is None


def test_member_list_is_recent_first_null_last_with_stable_id_tiebreak(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    recent_at = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    tied_at = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    recent = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="recent@corp.com",
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        last_seen_at=recent_at,
    )
    tied_later_id = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="tie-b@corp.com",
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        last_seen_at=tied_at,
    )
    tied_earlier_id = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="tie-a@corp.com",
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        last_seen_at=tied_at,
    )
    never_seen = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="never@corp.com",
        user_id=UUID("00000000-0000-0000-0000-000000000004"),
    )
    headers = bearer_headers(seeded_org.id, "admin")
    expected = [
        str(recent.id),
        str(tied_earlier_id.id),
        str(tied_later_id.id),
        str(never_seen.id),
    ]

    first = client.get("/api/v1/users", headers=headers)
    second = client.get("/api/v1/users", headers=headers)

    assert first.status_code == second.status_code == 200
    assert [row["user_id"] for row in first.json()["data"]] == expected
    assert [row["user_id"] for row in second.json()["data"]] == expected
    assert first.json()["data"][-1]["last_seen_at"] is None


def test_viewer_cannot_list_members(
    client: TestClient, seeded_org: Org, bearer_headers
) -> None:
    response = client.get(
        "/api/v1/users", headers=bearer_headers(seeded_org.id, "viewer")
    )

    _assert_error_envelope(response, 403, "forbidden")
    assert response.json()["error"]["details"] == {}


def test_member_list_without_bearer_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/users")

    _assert_error_envelope(response, 401, "unauthorized")
    assert response.json()["error"]["details"] == {}


def test_promote_returns_member_and_subsequent_own_profile_reports_admin(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="admin@corp.com",
        role="admin",
    )
    viewer = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="viewer@corp.com",
    )

    response = client.patch(
        f"/api/v1/users/{viewer.id}",
        headers=_headers(admin),
        json={"role": "admin"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(viewer.id),
        "email": "viewer@corp.com",
        "role": "admin",
        "last_seen_at": None,
    }
    administrative_session.expire_all()
    promoted = administrative_session.get(User, viewer.id)
    assert promoted is not None
    assert promoted.role == "admin"

    own_profile = client.get("/api/v1/users/me", headers=_headers(promoted))

    assert own_profile.status_code == 200
    assert own_profile.json() == {
        "user_id": str(viewer.id),
        "email": "viewer@corp.com",
        "role": "admin",
    }


def test_demote_succeeds_and_repeating_the_same_role_is_idempotent(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    caller = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="caller@corp.com",
        role="admin",
    )
    target = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="target@corp.com",
        role="admin",
    )

    demoted = client.patch(
        f"/api/v1/users/{target.id}",
        headers=_headers(caller),
        json={"role": "viewer"},
    )
    repeated = client.patch(
        f"/api/v1/users/{target.id}",
        headers=_headers(caller),
        json={"role": "viewer"},
    )

    assert demoted.status_code == repeated.status_code == 200
    assert demoted.json()["role"] == repeated.json()["role"] == "viewer"
    administrative_session.expire_all()
    persisted = administrative_session.get(User, target.id)
    assert persisted is not None
    assert persisted.role == "viewer"


def test_self_target_returns_exact_409_envelope_and_preserves_role(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="admin@corp.com",
        role="admin",
    )

    response = client.patch(
        f"/api/v1/users/{admin.id}",
        headers=_headers(admin),
        json={"role": "viewer"},
    )

    assert response.status_code not in {403, 404}
    _assert_error_envelope(
        response,
        409,
        "self_target",
        message="You cannot change your own role.",
    )
    assert response.json()["error"]["details"] == {}
    administrative_session.expire_all()
    persisted = administrative_session.get(User, admin.id)
    assert persisted is not None
    assert persisted.role == "admin"


def test_last_admin_service_error_maps_to_durable_409_envelope(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    target = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="last-admin@corp.com",
        role="admin",
    )
    caller = CallerIdentity(sub=uuid4(), org_id=seeded_org.id, role="admin")

    def _override_require_admin() -> CallerIdentity:
        return caller

    app.dependency_overrides[require_admin] = _override_require_admin
    try:
        response = client.patch(
            f"/api/v1/users/{target.id}", json={"role": "viewer"}
        )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    _assert_error_envelope(
        response,
        409,
        "last_admin",
        message="Add another admin before changing this role.",
    )
    assert response.json()["error"]["details"] == {}
    administrative_session.expire_all()
    persisted = administrative_session.get(User, target.id)
    assert persisted is not None
    assert persisted.role == "admin"
    assert users.count_org_admins(administrative_session, org_id=seeded_org.id) == 1


def test_foreign_org_target_returns_404_not_403_and_is_untouched(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="admin@corp.com",
        role="admin",
    )
    other_org = Org(name="Other Org")
    administrative_session.add(other_org)
    administrative_session.commit()
    administrative_session.refresh(other_org)
    foreign = _seed_user(
        administrative_session,
        org_id=other_org.id,
        email="foreign@corp.com",
    )

    response = client.patch(
        f"/api/v1/users/{foreign.id}",
        headers=_headers(admin),
        json={"role": "admin"},
    )

    assert response.status_code != 403
    _assert_error_envelope(response, 404, "not_found")
    administrative_session.expire_all()
    persisted = administrative_session.get(User, foreign.id)
    assert persisted is not None
    assert persisted.role == "viewer"


def test_unknown_user_returns_404(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="admin@corp.com",
        role="admin",
    )

    response = client.patch(
        f"/api/v1/users/{uuid4()}",
        headers=_headers(admin),
        json={"role": "viewer"},
    )

    _assert_error_envelope(response, 404, "not_found")


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"role": "owner"}, "role"),
        ({"role": "viewer", "email": "x@y.z"}, "email"),
    ],
)
def test_role_patch_rejects_bad_role_and_extra_field(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    payload: dict[str, str],
    field: str,
) -> None:
    admin = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="admin@corp.com",
        role="admin",
    )
    target = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="target@corp.com",
    )

    response = client.patch(
        f"/api/v1/users/{target.id}", headers=_headers(admin), json=payload
    )

    _assert_error_envelope(
        response, 422, "validation_error", details={"field": field}
    )
    administrative_session.expire_all()
    persisted = administrative_session.get(User, target.id)
    assert persisted is not None
    assert persisted.role == "viewer"


def test_viewer_cannot_patch_member_and_role_is_unchanged(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    viewer = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="viewer@corp.com",
    )
    target = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="target@corp.com",
    )

    response = client.patch(
        f"/api/v1/users/{target.id}",
        headers=_headers(viewer),
        json={"role": "admin"},
    )

    _assert_error_envelope(response, 403, "forbidden")
    administrative_session.expire_all()
    persisted = administrative_session.get(User, target.id)
    assert persisted is not None
    assert persisted.role == "viewer"


def test_role_patch_without_bearer_returns_401_and_preserves_role(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    target = _seed_user(
        administrative_session,
        org_id=seeded_org.id,
        email="target@corp.com",
    )

    response = client.patch(
        f"/api/v1/users/{target.id}", json={"role": "admin"}
    )

    _assert_error_envelope(response, 401, "unauthorized")
    administrative_session.expire_all()
    persisted = administrative_session.get(User, target.id)
    assert persisted is not None
    assert persisted.role == "viewer"


def test_real_patch_preflight_is_allowed(client: TestClient) -> None:
    response = client.options(
        f"/api/v1/users/{uuid4()}",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "PATCH" in response.headers["access-control-allow-methods"]
