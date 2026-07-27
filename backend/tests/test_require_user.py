from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import jwt
from api.core.config import get_settings
from api.dependencies.auth import CallerIdentity, require_admin, require_user
from api.models.persistence import utc_now
from api.services.tokens import create_access_token
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/whoami")
def whoami(caller: CallerIdentity = Depends(require_user)) -> CallerIdentity:
    return caller


@app.get("/admin-only")
def admin_only(caller: CallerIdentity = Depends(require_admin)) -> CallerIdentity:
    return caller


client = TestClient(app)


def _expired_token(user_id, org_id, role) -> str:
    settings = get_settings()
    now = utc_now()
    claims = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=1),
    }
    return jwt.encode(
        claims, settings.jwt_signing_secret.get_secret_value(), algorithm="HS256"
    )


def test_valid_bearer_resolves_caller_identity():
    user_id = uuid4()
    org_id = uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id, role="admin")

    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == str(user_id)
    assert body["org_id"] == str(org_id)
    assert body["role"] == "admin"


def test_missing_authorization_header_returns_401():
    response = client.get("/whoami")

    assert response.status_code == 401


def test_malformed_bearer_returns_401():
    response = client.get("/whoami", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_expired_token_returns_401():
    token = _expired_token(uuid4(), uuid4(), "admin")

    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_admin_token_allowed_by_require_admin():
    token = create_access_token(user_id=uuid4(), org_id=uuid4(), role="admin")

    response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_viewer_token_rejected_by_require_admin_with_403_not_401():
    token = create_access_token(user_id=uuid4(), org_id=uuid4(), role="viewer")

    response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.status_code != 401


def test_missing_token_rejected_by_require_admin_with_401():
    response = client.get("/admin-only")

    assert response.status_code == 401


def test_require_admin_depends_on_require_user_in_dependency_chain():
    admin_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/admin-only"
    )
    admin_dependant = admin_route.dependant.dependencies[0]
    nested_calls = {
        sub_dependant.call for sub_dependant in admin_dependant.dependencies
    }

    assert admin_dependant.call is require_admin
    assert require_user in nested_calls


def test_unknown_role_rejected_by_require_admin_with_403():
    token = create_access_token(user_id=uuid4(), org_id=uuid4(), role="superuser")

    response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_expired_token_rejected_by_require_admin_with_401_not_403():
    token = _expired_token(uuid4(), uuid4(), "admin")

    response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_malformed_bearer_rejected_by_require_admin_with_401_not_403():
    response = client.get(
        "/admin-only", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401
