from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.identity import Invite, Org
from api.models.persistence import utc_now
from api.services.tokens import hash_token
from fastapi.testclient import TestClient
from sqlmodel import Session, select

VALID_PASSWORD = "Xk9$mQvL2pTz"


def _assert_error_envelope(
    response,
    status_code: int,
    code: str,
    message: str,
) -> None:
    assert response.status_code == status_code
    assert response.json() == {
        "error": {"code": code, "message": message, "details": {}}
    }


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def runtime_client(runtime_session: Session) -> TestClient:
    def _override_get_session():
        yield runtime_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_org(session: Session, name: str) -> Org:
    org = Org(name=name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _seed_invite(
    session: Session,
    *,
    org_id: UUID,
    raw_token: str,
    email: str = "invitee@corp.com",
    role: str = "viewer",
    expires_delta: timedelta = timedelta(hours=1),
    consumed: bool = False,
    invite_id: UUID | None = None,
) -> Invite:
    invite = Invite(
        id=invite_id or uuid4(),
        org_id=org_id,
        email=email,
        role=role,
        token_hash=hash_token(raw_token),
        expires_at=utc_now() + expires_delta,
        consumed_at=utc_now() if consumed else None,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def _serialized_datetime(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def test_admin_lists_only_live_org_invites_with_exact_public_shape_and_no_tokens(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    live_raw = "live-secret-token"
    live = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token=live_raw,
        email="live@corp.com",
        role="admin",
    )
    consumed = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="consumed-secret-token",
        email="consumed@corp.com",
        consumed=True,
    )
    expired = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="expired-secret-token",
        email="expired@corp.com",
        expires_delta=timedelta(seconds=-1),
    )
    foreign_org = _seed_org(administrative_session, "Foreign Org")
    foreign = _seed_invite(
        administrative_session,
        org_id=foreign_org.id,
        raw_token="foreign-secret-token",
        email="foreign@corp.com",
    )

    response = client.get(
        "/api/v1/invites", headers=bearer_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {
                "invite_id": str(live.id),
                "email": live.email,
                "role": live.role,
                "expires_at": _serialized_datetime(live.expires_at),
            }
        ]
    }
    for invite in (live, consumed, expired, foreign):
        assert invite.token_hash not in response.text
    for raw_token in (
        live_raw,
        "consumed-secret-token",
        "expired-secret-token",
        "foreign-secret-token",
    ):
        assert raw_token not in response.text
    assert "token_hash" not in response.text
    assert "invite_token" not in response.text
    assert str(consumed.id) not in response.text
    assert str(expired.id) not in response.text
    assert str(foreign.id) not in response.text


def test_pending_invites_are_ordered_by_expiry_then_id_across_repeated_calls(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    soon = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="soon-token",
        email="soon@corp.com",
        expires_delta=timedelta(minutes=10),
        invite_id=UUID("00000000-0000-0000-0000-000000000004"),
    )
    tied_later_id = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="tie-later-token",
        email="tie-later@corp.com",
        expires_delta=timedelta(hours=1),
        invite_id=UUID("00000000-0000-0000-0000-000000000003"),
    )
    tied_earlier_id = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="tie-earlier-token",
        email="tie-earlier@corp.com",
        expires_delta=timedelta(hours=1),
        invite_id=UUID("00000000-0000-0000-0000-000000000002"),
    )
    later = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="later-token",
        email="later@corp.com",
        expires_delta=timedelta(hours=2),
        invite_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    tied_later_id.expires_at = tied_earlier_id.expires_at
    administrative_session.add(tied_later_id)
    administrative_session.commit()
    expected = [
        str(soon.id),
        str(tied_earlier_id.id),
        str(tied_later_id.id),
        str(later.id),
    ]
    headers = bearer_headers(seeded_org.id, "admin")

    first = client.get("/api/v1/invites", headers=headers)
    second = client.get("/api/v1/invites", headers=headers)

    assert first.status_code == second.status_code == 200
    assert [row["invite_id"] for row in first.json()["data"]] == expected
    assert [row["invite_id"] for row in second.json()["data"]] == expected


def test_viewer_cannot_list_invites(
    client: TestClient, seeded_org: Org, bearer_headers
) -> None:
    response = client.get(
        "/api/v1/invites", headers=bearer_headers(seeded_org.id, "viewer")
    )

    _assert_error_envelope(response, 403, "forbidden", "Admin role required")


def test_revoke_returns_204_hard_deletes_and_invalidates_lookup_and_accept(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    raw_token = "revoked-real-route-token"
    invite = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token=raw_token,
    )

    revoked = client.delete(
        f"/api/v1/invites/{invite.id}",
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert revoked.status_code == 204
    assert revoked.content == b""
    administrative_session.expire_all()
    assert administrative_session.get(Invite, invite.id) is None

    expected_gone = {
        "error": {
            "code": "invalid_invite_token",
            "message": "invalid or expired invite token",
            "details": {},
        }
    }
    lookup = client.post("/api/v1/invites/lookup", json={"token": raw_token})
    accepted = client.post(
        "/api/v1/invites/accept",
        json={"token": raw_token, "password": VALID_PASSWORD},
    )
    assert lookup.status_code == accepted.status_code == 410
    assert lookup.json() == accepted.json() == expected_gone


def test_reinvite_after_revoke_succeeds(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
    sent_emails,
) -> None:
    sent_emails()
    invite = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="old-token",
        email="retry@corp.com",
    )
    headers = bearer_headers(seeded_org.id, "admin")
    revoked = client.delete(f"/api/v1/invites/{invite.id}", headers=headers)

    response = client.post(
        "/api/v1/invites",
        headers=headers,
        json={"email": invite.email, "role": "admin"},
    )

    assert revoked.status_code == 204
    assert response.status_code == 201
    assert set(response.json()) == {"invite_token", "expires_at"}
    administrative_session.expire_all()
    rows = administrative_session.exec(
        select(Invite).where(Invite.email == invite.email)
    ).all()
    assert len(rows) == 1
    assert rows[0].id != invite.id
    assert rows[0].role == "admin"


@pytest.mark.parametrize("case", ["consumed", "expired", "foreign", "unknown"])
def test_revoke_non_pending_or_inaccessible_invite_returns_exact_404_and_preserves_row(
    case: str,
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    invite: Invite | None
    if case == "unknown":
        invite = None
        invite_id = uuid4()
    else:
        org_id = seeded_org.id
        if case == "foreign":
            org_id = _seed_org(administrative_session, "Foreign Org").id
        invite = _seed_invite(
            administrative_session,
            org_id=org_id,
            raw_token=f"{case}-token",
            consumed=case == "consumed",
            expires_delta=(
                timedelta(seconds=-1) if case == "expired" else timedelta(hours=1)
            ),
        )
        invite_id = invite.id

    response = client.delete(
        f"/api/v1/invites/{invite_id}",
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    if case == "foreign":
        assert response.status_code != 403
    _assert_error_envelope(response, 404, "not_found", "Invite not found")
    if invite is not None:
        administrative_session.expire_all()
        assert administrative_session.get(Invite, invite.id) is not None


def test_viewer_cannot_revoke_and_invite_survives(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    invite = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="viewer-refused-token",
    )

    response = client.delete(
        f"/api/v1/invites/{invite.id}",
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    _assert_error_envelope(response, 403, "forbidden", "Admin role required")
    administrative_session.expire_all()
    assert administrative_session.get(Invite, invite.id) is not None


@pytest.mark.parametrize("method", ["list", "revoke"])
def test_invite_admin_routes_without_bearer_return_exact_401_and_do_not_revoke(
    method: str,
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
) -> None:
    invite = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token=f"no-bearer-{method}-token",
    )
    response = (
        client.get("/api/v1/invites")
        if method == "list"
        else client.delete(f"/api/v1/invites/{invite.id}")
    )

    _assert_error_envelope(response, 401, "unauthorized", "Not authenticated")
    administrative_session.expire_all()
    assert administrative_session.get(Invite, invite.id) is not None


def test_runtime_role_can_revoke_and_commit(
    runtime_client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    invite = _seed_invite(
        administrative_session,
        org_id=seeded_org.id,
        raw_token="runtime-delete-token",
    )
    invite_id = invite.id

    response = runtime_client.delete(
        f"/api/v1/invites/{invite_id}",
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 204
    assert response.content == b""
    administrative_session.expire_all()
    assert administrative_session.get(Invite, invite_id) is None
