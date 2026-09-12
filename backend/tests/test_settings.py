from __future__ import annotations

import importlib
import importlib.metadata
from collections.abc import Callable
from uuid import UUID

import api.main as main
import api.services.nvd as nvd_module
import pytest
import sqlalchemy as sa
from api.core.config import Settings, get_settings
from api.db import session
from api.db.session import reset_db_state
from api.models.identity import Org
from api.models.persistence import NvdCacheRecord
from api.services.nvd import NvdClient
from api.services.tokens import decode_access_token
from pydantic import ValidationError
from sqlmodel import Session


def test_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "prefix",
    [
        "postgres://",
        "postgresql://",
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
    ],
)
def test_accepted_postgres_prefixes_validate(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{prefix}user:pass@host/db")

    settings = Settings()

    assert settings.database_url.get_secret_value() == f"{prefix}user:pass@host/db"


@pytest.mark.parametrize(
    "url",
    ["sqlite:///./scanner.db", "mysql://user:pass@host/db", "mongodb://host/db"],
)
def test_non_postgres_urls_are_rejected(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError):
        Settings()


def test_carried_fields_read_from_env_with_correct_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("KEV_API_BASE_URL", "https://example.test/kev")
    monkeypatch.setenv("KEV_CACHE_TTL_HOURS", "1")
    monkeypatch.setenv("EPSS_API_BASE_URL", "https://example.test/epss")
    monkeypatch.setenv("EPSS_CACHE_TTL_HOURS", "2")
    monkeypatch.setenv("NVD_API_BASE_URL", "https://example.test/nvd")
    monkeypatch.setenv("NVD_CACHE_TTL_HOURS", "3")
    monkeypatch.setenv("ENRICHMENT_POLL_INTERVAL_SECONDS", "1.5")
    monkeypatch.setenv("ENRICHMENT_BATCH_SIZE", "7")
    monkeypatch.setenv("AI_ENABLED", "true")

    settings = Settings()

    assert settings.kev_api_base_url == "https://example.test/kev"
    assert settings.kev_cache_ttl_hours == 1
    assert settings.epss_api_base_url == "https://example.test/epss"
    assert settings.epss_cache_ttl_hours == 2
    assert settings.nvd_api_base_url == "https://example.test/nvd"
    assert settings.nvd_cache_ttl_hours == 3
    assert settings.enrichment_poll_interval_seconds == 1.5
    assert settings.enrichment_batch_size == 7
    assert settings.ai_enabled is True


def test_carried_fields_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    for var in (
        "KEV_API_BASE_URL",
        "KEV_CACHE_TTL_HOURS",
        "EPSS_API_BASE_URL",
        "EPSS_CACHE_TTL_HOURS",
        "NVD_API_BASE_URL",
        "NVD_CACHE_TTL_HOURS",
        "NVD_API_KEY",
        "ENRICHMENT_POLL_INTERVAL_SECONDS",
        "ENRICHMENT_BATCH_SIZE",
        "AI_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings()

    assert settings.kev_api_base_url == (
        "https://www.cisa.gov/sites/default/files/feeds/"
        "known_exploited_vulnerabilities.json"
    )
    assert settings.kev_cache_ttl_hours == 24
    assert settings.epss_api_base_url == "https://api.first.org/data/v1/epss"
    assert settings.epss_cache_ttl_hours == 24
    assert settings.nvd_api_base_url == (
        "https://services.nvd.nist.gov/rest/json/cves/2.0"
    )
    assert settings.nvd_cache_ttl_hours == 12
    assert settings.nvd_api_key is None
    assert settings.enrichment_poll_interval_seconds == 5.0
    assert settings.enrichment_batch_size == 10
    assert settings.ai_enabled is False


def test_auth_settings_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    for var in (
        "ACCESS_TOKEN_TTL_MINUTES",
        "REFRESH_TOKEN_TTL_DAYS",
        "REFRESH_COOKIE_SECURE",
        "CORS_ALLOWED_ORIGINS",
        "RESET_TOKEN_TTL_MINUTES",
        "HIBP_ENABLED",
        "HIBP_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings()

    assert settings.access_token_ttl_minutes == 15
    assert settings.refresh_token_ttl_days == 7
    assert settings.refresh_cookie_secure is True
    assert settings.cors_allowed_origins == ""
    assert settings.reset_token_ttl_minutes == 60
    assert settings.hibp_enabled is True
    assert settings.hibp_timeout_seconds == 2


def test_device_sig_and_invite_settings_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    for var in ("DEVICE_SIG_MAX_SKEW_SECONDS", "INVITE_TTL_HOURS"):
        monkeypatch.delenv(var, raising=False)

    settings = Settings()

    assert settings.device_sig_max_skew_seconds == 300
    assert settings.invite_ttl_hours == 48


def test_device_sig_and_invite_settings_read_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("DEVICE_SIG_MAX_SKEW_SECONDS", "120")
    monkeypatch.setenv("INVITE_TTL_HOURS", "72")

    settings = Settings()

    assert settings.device_sig_max_skew_seconds == 120
    assert settings.invite_ttl_hours == 72


def test_bearer_headers_fixture_builds_token_for_seeded_org(
    seeded_org: Org,
    bearer_headers: Callable[[UUID, str], dict[str, str]],
) -> None:
    headers = bearer_headers(seeded_org.id, "admin")

    scheme, token = headers["Authorization"].split(" ", 1)
    claims = decode_access_token(token)

    assert scheme == "Bearer"
    assert claims["org_id"] == str(seeded_org.id)
    assert claims["role"] == "admin"


def test_missing_jwt_signing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.delenv("JWT_SIGNING_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_unused_auth_and_cors_settings_are_absent() -> None:
    assert "jwt_secret" not in Settings.model_fields
    assert "agent_hmac_secret" not in Settings.model_fields
    assert "cors_origins" not in Settings.model_fields


def test_settings_representation_and_serialization_redact_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:hunter2@host/db")
    monkeypatch.setenv("NVD_API_KEY", "top-secret-nvd-key")

    settings = Settings()

    rendered = repr(settings) + str(settings) + str(settings.model_dump())
    rendered += settings.model_dump_json()

    assert "hunter2" not in rendered
    assert "postgresql://user:hunter2@host/db" not in rendered
    assert "top-secret-nvd-key" not in rendered


def test_invalid_database_url_error_hides_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_url = "sqlite:///hunter2-secret-path.db"
    monkeypatch.setenv("DATABASE_URL", secret_url)

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    message = str(excinfo.value)
    assert secret_url not in message
    assert "hunter2" not in message


def test_missing_database_url_fails_before_engine_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_db_state()
    calls: list[bool] = []
    with monkeypatch.context() as ctx:
        ctx.delenv("DATABASE_URL", raising=False)
        ctx.setattr(session, "create_engine", lambda *a, **k: calls.append(True))
        with pytest.raises(ValidationError):
            importlib.reload(main)
    importlib.reload(main)
    reset_db_state()
    assert calls == []


def test_unreachable_valid_url_constructs_app_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_db_state()
    calls: list[bool] = []
    with monkeypatch.context() as ctx:
        ctx.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/x")
        ctx.setattr(session, "create_engine", lambda *a, **k: calls.append(True))
        importlib.reload(main)
        assert main.app.version == importlib.metadata.version("backend-api")
    importlib.reload(main)
    reset_db_state()
    assert calls == []


def test_nvd_client_delivers_key_in_header_without_exposing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("NVD_API_KEY", "top-secret-nvd-key")
    get_settings.cache_clear()

    engine = sa.create_engine("sqlite://")
    NvdCacheRecord.metadata.create_all(engine, tables=[NvdCacheRecord.__table__])

    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"vulnerabilities": []}

    class _FakeClient:
        def __init__(self, timeout: float | None = None, headers: dict | None = None):
            captured["headers"] = headers

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *exc_info: object) -> bool:
            return False

        def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(nvd_module.httpx, "Client", _FakeClient)

    client = NvdClient()
    with Session(engine) as db_session:
        client.query_by_cve(db_session, "CVE-2024-0001")

    get_settings.cache_clear()

    assert captured["headers"] == {"apiKey": "top-secret-nvd-key"}
    assert "top-secret-nvd-key" not in repr(client.api_key)
    assert "top-secret-nvd-key" not in str(client.api_key)
