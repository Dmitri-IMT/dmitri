"""Auth and paging rules that every read route shares.

Per-endpoint behaviour lives in ``test_read_hosts.py``, ``test_read_scans.py``
and ``test_read_findings.py``; this module only covers what the routes have in
common -- bearer handling, the viewer role, unknown orgs and paging bounds.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from api.core.config import get_settings
from api.models.persistence import utc_now
from read_factories import seed_read_graph
from sqlmodel import Session
from starlette.testclient import TestClient

READ_PATHS = (
    "/api/v1/hosts",
    "/api/v1/hosts/{host_id}",
    "/api/v1/scans",
    "/api/v1/scans/{scan_id}",
    "/api/v1/findings",
)

LIST_ENDPOINTS = ("/api/v1/scans", "/api/v1/findings")


def _resolved_path(path: str, seeded: dict) -> str:
    return path.format(
        host_id=seeded["host"].id, scan_id=seeded["scan"].scan_id
    )


def _expired_bearer_headers(org_id: UUID, role: str) -> dict[str, str]:
    settings = get_settings()
    now = utc_now()
    claims = {
        "sub": str(uuid4()),
        "org_id": str(org_id),
        "role": role,
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=1),
    }
    token = jwt.encode(
        claims, settings.jwt_signing_secret.get_secret_value(), algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_without_bearer_returns_401(
    client: TestClient, administrative_session: Session, path: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(_resolved_path(path, seeded))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_with_garbage_bearer_returns_401(
    client: TestClient, administrative_session: Session, path: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        _resolved_path(path, seeded),
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_with_expired_bearer_returns_401(
    client: TestClient, administrative_session: Session, path: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        _resolved_path(path, seeded),
        headers=_expired_bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("path", READ_PATHS)
def test_read_route_with_viewer_token_never_returns_403(
    client: TestClient, administrative_session: Session, bearer_headers, path: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        _resolved_path(path, seeded), headers=bearer_headers(seeded["org"].id, "viewer")
    )
    assert response.status_code != 403
    assert response.status_code == 200


def test_nonexistent_org_token_list_hosts_returns_empty(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seed_read_graph(administrative_session)
    response = client.get("/api/v1/hosts", headers=bearer_headers(uuid4(), "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_nonexistent_org_token_list_findings_returns_empty(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seed_read_graph(administrative_session)
    response = client.get("/api/v1/findings", headers=bearer_headers(uuid4(), "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["data"] == []


def test_nonexistent_org_token_get_host_returns_404(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/hosts/{seeded['host'].id}", headers=bearer_headers(uuid4(), "admin")
    )
    assert response.status_code == 404


def test_nonexistent_org_token_get_scan_returns_404(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"/api/v1/scans/{seeded['scan'].scan_id}",
        headers=bearer_headers(uuid4(), "admin"),
    )
    assert response.status_code == 404


@pytest.mark.parametrize("endpoint", LIST_ENDPOINTS)
@pytest.mark.parametrize(
    "query",
    ("per_page=101", "per_page=0", "page=0", "page=-1"),
)
def test_list_invalid_paging_returns_validation_error(
    client: TestClient,
    administrative_session: Session,
    bearer_headers,
    endpoint: str,
    query: str,
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"{endpoint}?{query}",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("endpoint", LIST_ENDPOINTS)
def test_list_per_page_at_max_succeeds(
    client: TestClient, administrative_session: Session, bearer_headers, endpoint: str
) -> None:
    seeded = seed_read_graph(administrative_session)
    response = client.get(
        f"{endpoint}?per_page=100",
        headers=bearer_headers(seeded["org"].id, "admin"),
    )
    assert response.status_code == 200
