from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.identity import Org, User
from api.models.persistence import FindingRecord, HostRecord, ScanRecord, utc_now
from api.models.session import PasswordResetToken, RefreshToken
from api.services.passwords import hash_password
from api.services.tokens import create_access_token, hash_token
from fastapi.testclient import TestClient
from read_factories import make_finding, make_host, make_scan, make_scan_host
from sqlmodel import Session, select

VALID_PASSWORD = "Xk9$mQvL2pTz"


def _assert_error_envelope(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert "detail" not in body
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["details"] == {}


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
    session: Session, *, org_id: UUID, email: str, role: str = "viewer"
) -> User:
    user = User(
        org_id=org_id,
        email=email,
        password_hash=hash_password(VALID_PASSWORD),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id, org_id=user.org_id, role=user.role
    )
    return {"Authorization": f"Bearer {token}"}


def test_admin_removes_member_returns_204_without_set_cookie(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    member = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )

    response = client.delete(f"/api/v1/users/{member.id}", headers=_headers(admin))

    assert response.status_code == 204
    assert "set-cookie" not in response.headers
    assert administrative_session.get(User, member.id) is None


def test_viewer_removes_themselves_returns_204_without_set_cookie(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    viewer = _seed_user(
        administrative_session, org_id=seeded_org.id, email="v@corp.com"
    )

    response = client.delete("/api/v1/users/me", headers=_headers(viewer))

    assert response.status_code == 204
    assert "set-cookie" not in response.headers
    assert administrative_session.get(User, viewer.id) is None


def test_admin_removes_themselves_when_second_admin_exists(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    first = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    _seed_user(
        administrative_session, org_id=seeded_org.id, email="b@corp.com", role="admin"
    )

    response = client.delete("/api/v1/users/me", headers=_headers(first))

    assert response.status_code == 204
    assert administrative_session.get(User, first.id) is None


def test_sole_admin_self_removal_is_refused_then_unblocked_by_a_second_admin(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    _seed_user(administrative_session, org_id=seeded_org.id, email="v@corp.com")

    refused = client.delete("/api/v1/users/me", headers=_headers(admin))

    _assert_error_envelope(refused, 409, "last_admin")
    assert refused.json()["error"]["message"] == (
        "Add another admin before removing your account."
    )
    assert administrative_session.get(User, admin.id) is not None

    _seed_user(
        administrative_session, org_id=seeded_org.id, email="b@corp.com", role="admin"
    )

    allowed = client.delete("/api/v1/users/me", headers=_headers(admin))

    assert allowed.status_code == 204
    assert administrative_session.get(User, admin.id) is None


def test_viewer_removing_another_member_is_forbidden(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    viewer = _seed_user(
        administrative_session, org_id=seeded_org.id, email="v@corp.com"
    )
    target = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )

    response = client.delete(f"/api/v1/users/{target.id}", headers=_headers(viewer))

    _assert_error_envelope(response, 403, "forbidden")
    assert administrative_session.get(User, target.id) is not None


def test_admin_self_targeting_returns_409_self_target_not_404(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    _seed_user(
        administrative_session, org_id=seeded_org.id, email="b@corp.com", role="admin"
    )

    response = client.delete(f"/api/v1/users/{admin.id}", headers=_headers(admin))

    assert response.status_code != 404
    _assert_error_envelope(response, 409, "self_target")
    assert response.json()["error"]["message"] == (
        "Remove your account from Settings instead."
    )
    assert administrative_session.get(User, admin.id) is not None


def test_foreign_org_target_returns_404_not_403(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    other_org = Org(name="Other Org")
    administrative_session.add(other_org)
    administrative_session.commit()
    administrative_session.refresh(other_org)
    foreigner = _seed_user(
        administrative_session, org_id=other_org.id, email="f@corp.com"
    )

    response = client.delete(f"/api/v1/users/{foreigner.id}", headers=_headers(admin))

    assert response.status_code != 403
    _assert_error_envelope(response, 404, "not_found")
    assert administrative_session.get(User, foreigner.id) is not None


def test_unknown_id_and_retry_after_completed_removal_return_404(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    member = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )

    unknown = client.delete(f"/api/v1/users/{uuid4()}", headers=_headers(admin))

    _assert_error_envelope(unknown, 404, "not_found")

    assert (
        client.delete(
            f"/api/v1/users/{member.id}", headers=_headers(admin)
        ).status_code
        == 204
    )
    retry = client.delete(f"/api/v1/users/{member.id}", headers=_headers(admin))

    _assert_error_envelope(retry, 404, "not_found")


def test_retry_after_completed_self_removal_returns_401(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    viewer = _seed_user(
        administrative_session, org_id=seeded_org.id, email="v@corp.com"
    )
    headers = _headers(viewer)

    assert client.delete("/api/v1/users/me", headers=headers).status_code == 204
    retry = client.delete("/api/v1/users/me", headers=headers)

    _assert_error_envelope(retry, 401, "unauthorized")


@pytest.mark.parametrize(
    "path", ("/api/v1/users/me", f"/api/v1/users/{uuid4()}")
)
def test_delete_without_bearer_returns_401_envelope(
    client: TestClient, administrative_session: Session, seeded_org: Org, path: str
) -> None:
    member = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )

    _assert_error_envelope(client.delete(path), 401, "unauthorized")
    assert administrative_session.get(User, member.id) is not None


def test_removal_cascades_refresh_and_password_reset_tokens(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    member = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )
    refresh = RefreshToken(
        user_id=member.id,
        family_id=uuid4(),
        token_hash=hash_token("refresh-raw"),
        family_expires_at=utc_now() + timedelta(days=7),
    )
    reset = PasswordResetToken(
        user_id=member.id,
        token_hash=hash_token("reset-raw"),
        expires_at=utc_now() + timedelta(minutes=30),
    )
    administrative_session.add(refresh)
    administrative_session.add(reset)
    administrative_session.commit()
    member_id = member.id

    response = client.delete(f"/api/v1/users/{member_id}", headers=_headers(admin))

    assert response.status_code == 204
    assert (
        administrative_session.exec(
            select(RefreshToken).where(RefreshToken.user_id == member_id)
        ).first()
        is None
    )
    assert (
        administrative_session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == member_id
            )
        ).first()
        is None
    )


def test_removal_ends_the_session_and_row_backed_identity(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    member = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": VALID_PASSWORD},
    )
    assert login.status_code == 200
    member_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    assert (
        client.delete(
            f"/api/v1/users/{member.id}", headers=_headers(admin)
        ).status_code
        == 204
    )

    _assert_error_envelope(client.post("/api/v1/auth/refresh"), 401, "unauthorized")
    _assert_error_envelope(
        client.get("/api/v1/users/me", headers=member_headers), 401, "unauthorized"
    )
    _assert_error_envelope(
        client.post(
            "/api/v1/auth/login",
            json={"email": member.email, "password": VALID_PASSWORD},
        ),
        401,
        "unauthorized",
    )


def test_org_data_survives_removal_and_the_address_is_invitable_again(
    client: TestClient, administrative_session: Session, seeded_org: Org
) -> None:
    admin = _seed_user(
        administrative_session, org_id=seeded_org.id, email="a@corp.com", role="admin"
    )
    member = _seed_user(
        administrative_session, org_id=seeded_org.id, email="m@corp.com"
    )
    agent = Agent(
        org_id=seeded_org.id, display_name="Pi", public_key=b"public-key-bytes"
    )
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)
    host = make_host(administrative_session, seeded_org.id, "192.168.1.10")
    scan = make_scan(administrative_session, seeded_org.id)
    scan_host = make_scan_host(
        administrative_session, scan.scan_id, host.id, "192.168.1.10"
    )
    finding = make_finding(
        administrative_session, scan.scan_id, scan_host.id, "dedupe-1"
    )

    assert (
        client.delete(
            f"/api/v1/users/{member.id}", headers=_headers(admin)
        ).status_code
        == 204
    )

    assert administrative_session.get(Agent, agent.id) is not None
    assert administrative_session.exec(
        select(HostRecord).where(HostRecord.id == host.id)
    ).first() is not None
    assert administrative_session.exec(
        select(ScanRecord).where(ScanRecord.scan_id == scan.scan_id)
    ).first() is not None
    assert administrative_session.exec(
        select(FindingRecord).where(FindingRecord.finding_id == finding.finding_id)
    ).first() is not None

    reinvite = client.post(
        "/api/v1/invites",
        json={"email": member.email, "role": "viewer"},
        headers=_headers(admin),
    )

    assert reinvite.status_code == 201

    administrative_session.delete(agent)
    administrative_session.commit()
