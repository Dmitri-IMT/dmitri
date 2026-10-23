from __future__ import annotations

from functools import lru_cache
from typing import Literal, get_args

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.core.scan_mode import ScanMode

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
    ai_auto_analysis: bool = Field(default=False, alias="AI_AUTO_ANALYSIS")
    ai_model: str = Field(default="gpt-6-luna", alias="AI_MODEL")
    ai_api_key: SecretStr | None = Field(default=None, alias="AI_API_KEY")
    ai_max_findings: int = Field(default=10, ge=1, le=15, alias="AI_MAX_FINDINGS")
    ai_timeout_seconds: float = Field(
        default=120.0, gt=0, le=600, alias="AI_TIMEOUT_SECONDS"
    )
    ai_max_output_tokens: int = Field(
        default=25_000, ge=256, le=128_000, alias="AI_MAX_OUTPUT_TOKENS"
    )
    ai_reasoning_effort: Literal[
        "none", "low", "medium", "high", "xhigh", "max"
    ] = Field(default="high", alias="AI_REASONING_EFFORT")
    ai_max_attempts: int = Field(default=2, ge=1, le=5, alias="AI_MAX_ATTEMPTS")
    ai_retry_delay_seconds: float = Field(
        default=30.0, ge=0, le=3600, alias="AI_RETRY_DELAY_SECONDS"
    )
    ai_fix_record_ttl_fixed_days: int = Field(
        default=14, ge=1, le=90, alias="AI_FIX_RECORD_TTL_FIXED_DAYS"
    )
    ai_fix_record_ttl_unfixed_days: int = Field(
        default=2, ge=1, le=90, alias="AI_FIX_RECORD_TTL_UNFIXED_DAYS"
    )
    ai_research_max_tool_calls: int = Field(
        default=10, ge=1, le=20, alias="AI_RESEARCH_MAX_TOOL_CALLS"
    )
    ai_chat_max_tool_calls: int = Field(
        default=10, ge=1, le=20, alias="AI_CHAT_MAX_TOOL_CALLS"
    )
    ai_chat_daily_limit: int = Field(
        default=30, ge=1, le=1000, alias="AI_CHAT_DAILY_LIMIT"
    )
    ai_search_country: str | None = Field(
        default=None, pattern=r"^[A-Z]{2}$", alias="AI_SEARCH_COUNTRY"
    )
    ai_search_timezone: str | None = Field(default=None, alias="AI_SEARCH_TIMEZONE")
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
    agent_update_repository_url: str = Field(
        default="", alias="AGENT_UPDATE_REPOSITORY_URL"
    )
    agent_update_keyring_path: str = Field(
        default="", alias="AGENT_UPDATE_KEYRING_PATH"
    )
    agent_update_origin: str = Field(default="", alias="AGENT_UPDATE_ORIGIN")
    agent_update_suite: str = Field(default="", alias="AGENT_UPDATE_SUITE")
    agent_update_catalog_max_bytes: int = Field(
        default=1048576, ge=1024, le=10485760,
        alias="AGENT_UPDATE_CATALOG_MAX_BYTES",
    )
    agent_update_refresh_interval_seconds: float = Field(
        default=300, gt=0, le=86400,
        alias="AGENT_UPDATE_REFRESH_INTERVAL_SECONDS",
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
    command_max_duration_quick_seconds: int = Field(
        default=10800, gt=0, alias="COMMAND_MAX_DURATION_QUICK_SECONDS"
    )
    command_max_duration_standard_seconds: int = Field(
        default=28800, gt=0, alias="COMMAND_MAX_DURATION_STANDARD_SECONDS"
    )
    command_max_duration_extensive_seconds: int = Field(
        default=57600, gt=0, alias="COMMAND_MAX_DURATION_EXTENSIVE_SECONDS"
    )
    command_max_duration_nspi_seconds: int = Field(
        default=21600, gt=0, alias="COMMAND_MAX_DURATION_NSPI_SECONDS"
    )
    command_max_duration_max_seconds: int = Field(
        default=93600, gt=0, alias="COMMAND_MAX_DURATION_MAX_SECONDS"
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

    def command_max_duration_by_mode(self) -> dict[str, int]:
        return {
            mode: getattr(self, f"command_max_duration_{mode}_seconds")
            for mode in get_args(ScanMode)
        }

    @model_validator(mode="after")
    def _validate_command_max_duration(self) -> Settings:
        # Fails at startup, not on the first sweep, if a ScanMode has no field.
        self.command_max_duration_by_mode()
        max_seconds = self.command_max_duration_max_seconds
        extensive_seconds = self.command_max_duration_extensive_seconds
        if max_seconds < extensive_seconds:
            raise ValueError(
                "command_max_duration_max_seconds must be >= "
                "command_max_duration_extensive_seconds"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
