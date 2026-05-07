"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cache_backend: Literal["local", "redis"] = "local"
    cache_ttl_seconds: int = 300
    redis_url: str | None = None
    cors_origins: str | None = None
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"  # docker/k8s: use http://alloy:4318
    otel_service_name: str = "pestoengine"
    otel_export_interval_ms: int = 60_000

    @model_validator(mode="after")
    def _check_redis_url(self) -> "Settings":
        if self.cache_backend == "redis" and self.redis_url is None:
            raise ValueError("REDIS_URL must be set when CACHE_BACKEND=redis")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
