from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite:///./scanner.db", alias="DATABASE_URL")
    nvd_api_base_url: str = Field(
        default="https://services.nvd.nist.gov/rest/json/cves/2.0",
        alias="NVD_API_BASE_URL",
    )
    nvd_api_key: str | None = Field(default=None, alias="NVD_API_KEY")
    nvd_cache_ttl_hours: int = Field(default=12, alias="NVD_CACHE_TTL_HOURS")
    enrichment_poll_interval_seconds: float = Field(
        default=5.0,
        alias="ENRICHMENT_POLL_INTERVAL_SECONDS",
    )
    enrichment_batch_size: int = Field(
        default=10,
        alias="ENRICHMENT_BATCH_SIZE",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
        ],
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
