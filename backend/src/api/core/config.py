from __future__ import annotations

from functools import lru_cache

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
    enrichment_poll_interval_seconds: float = Field(
        default=5.0,
        alias="ENRICHMENT_POLL_INTERVAL_SECONDS",
    )
    enrichment_batch_size: int = Field(
        default=10,
        alias="ENRICHMENT_BATCH_SIZE",
    )
    jwt_signing_secret: SecretStr = Field(alias="JWT_SIGNING_SECRET")
    access_token_ttl_minutes: int = Field(
        default=15, alias="ACCESS_TOKEN_TTL_MINUTES"
    )
    refresh_token_ttl_days: int = Field(default=7, alias="REFRESH_TOKEN_TTL_DAYS")
    refresh_cookie_secure: bool = Field(default=True, alias="REFRESH_COOKIE_SECURE")
    cors_allowed_origins: str = Field(
        default="http://localhost:5173,https://app.vscanner.example.com",
        alias="CORS_ALLOWED_ORIGINS",
    )
    reset_token_ttl_minutes: int = Field(default=60, alias="RESET_TOKEN_TTL_MINUTES")
    hibp_enabled: bool = Field(default=True, alias="HIBP_ENABLED")
    hibp_timeout_seconds: float = Field(default=2, alias="HIBP_TIMEOUT_SECONDS")

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
