from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_POSTGRES_PREFIXES = (
    "postgres://",
    "postgresql://",
    "postgresql+psycopg://",
    "postgresql+asyncpg://",
)


def normalize_postgres_url(value: str, variable: str = "DATABASE_URL") -> str:
    if not value.startswith(_POSTGRES_PREFIXES):
        raise ValueError(f"{variable} must be a PostgreSQL connection URL.")
    return "postgresql+psycopg://" + value.split("://", 1)[1]


class Settings(BaseSettings):
    database_url: SecretStr = Field(alias="DATABASE_URL")
    ai_enabled: bool = Field(default=False, alias="AI_ENABLED")
    ai_model: str = Field(default="openai/gpt-oss-120b", alias="AI_MODEL")
    ai_api_key: SecretStr | None = Field(default=None, alias="AI_API_KEY")
    ai_api_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        alias="AI_API_BASE_URL",
    )
    ai_max_findings: int = Field(default=10, ge=1, le=15, alias="AI_MAX_FINDINGS")
    ai_timeout_seconds: float = Field(
        default=30.0, gt=0, le=120, alias="AI_TIMEOUT_SECONDS"
    )
    ai_max_output_tokens: int = Field(
        default=4096, ge=256, le=8192, alias="AI_MAX_OUTPUT_TOKENS"
    )
    ai_reasoning_effort: Literal["low", "medium", "high"] = Field(
        default="low", alias="AI_REASONING_EFFORT"
    )
    ai_max_attempts: int = Field(default=2, ge=1, le=5, alias="AI_MAX_ATTEMPTS")
    ai_retry_delay_seconds: float = Field(
        default=30.0, ge=0, le=3600, alias="AI_RETRY_DELAY_SECONDS"
    )
    ai_poll_interval_seconds: float = Field(
        default=5.0,
        alias="AI_POLL_INTERVAL_SECONDS",
    )
    kev_api_base_url: str = Field(
        default="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        alias="KEV_API_BASE_URL",
    )
    kev_cache_ttl_hours: int = Field(default=24, alias="KEV_CACHE_TTL_HOURS")
    epss_api_base_url: str = Field(
        default="https://api.first.org/data/v1/epss",
        alias="EPSS_API_BASE_URL",
    )
    epss_cache_ttl_hours: int = Field(default=24, alias="EPSS_CACHE_TTL_HOURS")
    nvd_api_base_url: str = Field(
        default="https://services.nvd.nist.gov/rest/json/cves/2.0",
        alias="NVD_API_BASE_URL",
    )
    nvd_api_key: SecretStr | None = Field(default=None, alias="NVD_API_KEY")
    nvd_cache_ttl_hours: int = Field(default=12, alias="NVD_CACHE_TTL_HOURS")
    nvd_min_request_interval_seconds: float = Field(
        default=6.0,
        ge=0,
        le=60,
        alias="NVD_MIN_REQUEST_INTERVAL_SECONDS",
    )
    enrichment_poll_interval_seconds: float = Field(
        default=5.0,
        alias="ENRICHMENT_POLL_INTERVAL_SECONDS",
    )
    enrichment_batch_size: int = Field(
        default=10,
        alias="ENRICHMENT_BATCH_SIZE",
    )
    enrichment_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="ENRICHMENT_MAX_ATTEMPTS",
    )
    enrichment_retry_delay_seconds: float = Field(
        default=30.0,
        ge=0,
        le=3600,
        alias="ENRICHMENT_RETRY_DELAY_SECONDS",
    )
    enrichment_stale_after_seconds: float = Field(
        default=120.0,
        gt=0,
        le=3600,
        alias="ENRICHMENT_STALE_AFTER_SECONDS",
    )
    jwt_signing_secret: SecretStr = Field(alias="JWT_SIGNING_SECRET")
    access_token_ttl_minutes: int = Field(
        default=15, alias="ACCESS_TOKEN_TTL_MINUTES"
    )
    refresh_token_ttl_days: int = Field(default=7, alias="REFRESH_TOKEN_TTL_DAYS")
    refresh_cookie_secure: bool = Field(default=True, alias="REFRESH_COOKIE_SECURE")
    # Fails closed: an unset CORS_ALLOWED_ORIGINS yields an empty allowlist, so the API
    # permits no browser origin at all. The previous default trusted a developer
    # workstation and a placeholder domain nobody owns, which — with
    # allow_credentials=True — made a missing variable a silent exposure.
    cors_allowed_origins: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")
    reset_token_ttl_minutes: int = Field(default=60, alias="RESET_TOKEN_TTL_MINUTES")
    hibp_enabled: bool = Field(default=True, alias="HIBP_ENABLED")
    hibp_timeout_seconds: float = Field(default=2, alias="HIBP_TIMEOUT_SECONDS")
    device_sig_max_skew_seconds: int = Field(
        default=300, alias="DEVICE_SIG_MAX_SKEW_SECONDS"
    )
    invite_ttl_hours: int = Field(default=48, alias="INVITE_TTL_HOURS")
    resend_api_key: SecretStr | None = Field(default=None, alias="RESEND_API_KEY")
    resend_api_base_url: str = Field(
        default="https://api.resend.com/emails",
        alias="RESEND_API_BASE_URL",
    )
    mail_from: str = Field(
        default="Dmitri <no-reply@mail.peirce.dev>",
        alias="MAIL_FROM",
    )
    mail_reply_to: str | None = Field(default=None, alias="MAIL_REPLY_TO")
    mail_timeout_seconds: float = Field(default=10.0, alias="MAIL_TIMEOUT_SECONDS")
    app_base_url: str = Field(
        default="https://dmitri.peirce.dev",
        alias="APP_BASE_URL",
    )
    command_disconnect_grace_seconds: int = Field(
        default=900, alias="COMMAND_DISCONNECT_GRACE_SECONDS"
    )
    industrial_observation_retention_days: int = Field(
        default=180, alias="INDUSTRIAL_OBSERVATION_RETENTION_DAYS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: SecretStr) -> SecretStr:
        normalize_postgres_url(value.get_secret_value())
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
