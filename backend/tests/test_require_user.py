from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import jwt
from api.core.config import get_settings
from api.dependencies.auth import CallerIdentity, require_user
from api.models.persistence import utc_now
from api.services.tokens import create_access_token
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/whoami")
def whoami(caller: CallerIdentity = Depends(require_user)) -> CallerIdentity:
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
