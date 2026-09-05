from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from api.main import app
from api.models.activity import ActivityRecord
from api.schemas.home import HomeSnapshot
from read_factories import seed_read_graph
from sqlmodel import Session
from starlette.testclient import TestClient


def _seed_activity(session: Session, org_id) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        ActivityRecord(
            org_id=org_id,
            kind="member_invited",
            occurred_at=now - timedelta(minutes=5),
            payload={
                "actor_email": "boss@example.com",
                "invite_email": "new@example.com",
            },
        )
    )
    session.add(
        ActivityRecord(
            org_id=org_id,
            kind="role_changed",
            occurred_at=now - timedelta(minutes=10),
            payload={
                "actor_email": "boss@example.com",
                "target_email": "new@example.com",
                "new_role": "admin",
            },
        )
    )
    session.commit()


def test_get_home_authed_returns_home_snapshot(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        "/api/v1/home", headers=bearer_headers(seeded["org"].id, "admin")
    )
    assert response.status_code == 200
    body = response.json()
    HomeSnapshot.model_validate(body)
    assert body["attention"]["page"] == 1
    assert body["events"]["page"] == 1
    assert body["activity"]["page"] == 1


@pytest.mark.parametrize(
    "param", ("attention_page", "events_page", "activity_page")
)
def test_get_home_page_zero_returns_422(
    client: TestClient, administrative_session: Session, bearer_headers, param: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/home?{param}=0",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422


def test_get_home_without_bearer_returns_401(client: TestClient) -> None:
    assert client.get("/api/v1/home").status_code == 401


def test_get_home_viewer_sees_same_rows_as_admin(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    _seed_activity(administrative_session, seeded["org"].id)

    admin = client.get(
        "/api/v1/home", headers=bearer_headers(seeded["org"].id, "admin")
    ).json()["activity"]
    viewer = client.get(
        "/api/v1/home", headers=bearer_headers(seeded["org"].id, "viewer")
    ).json()["activity"]

    assert viewer["total"] == admin["total"] == 2
    assert [row["kind"] for row in viewer["data"]] == [
        row["kind"] for row in admin["data"]
    ]
    assert [row["occurred_at"] for row in viewer["data"]] == [
        row["occurred_at"] for row in admin["data"]
    ]
    viewer_text = " ".join(row["text"] for row in viewer["data"])
    assert "boss@example.com" not in viewer_text
    assert viewer_text != " ".join(row["text"] for row in admin["data"])


def test_get_home_has_no_per_page(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    body = client.get(
        "/api/v1/home", headers=bearer_headers(seeded["org"].id, "admin")
    ).json()
    for page in ("attention", "events", "activity"):
        assert "per_page" not in body[page]

    params = app.openapi()["paths"]["/api/v1/home"]["get"].get("parameters", [])
    assert {p["name"] for p in params} == {
        "attention_page",
        "events_page",
        "activity_page",
    }


def test_get_home_empty_org_returns_empty_snapshot(
    client: TestClient, bearer_headers
) -> None:
    response = client.get("/api/v1/home", headers=bearer_headers(uuid4(), "viewer"))
    assert response.status_code == 200
    body = response.json()
    assert body["review_state"] == "blank"
    assert body["attention"]["data"] == []
    assert body["activity"]["total"] == 0
    assert body["latest_successful_scan"] is None
