"""Application settings loaded from environment variables."""

from contextvars import ContextVar
from functools import cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderId = Literal["yahoo", "alphavantage"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    base_currency: list[str] = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD"]
    cache_backend: Literal["local", "redis"] = "local"
    cache_ttl_seconds: int = Field(default=300, gt=0)
    local_cache_max_entries: int = Field(default=10_000, gt=0)
    quote_max_age_days: int = Field(default=7, ge=0, le=30)
    redis_timeout_seconds: float = Field(default=2, gt=0, le=30)
    provider_timeout_seconds: float = Field(default=10, gt=0, le=60)
    provider_request_budget_seconds: float = Field(default=30, gt=0, le=120)
    provider_concurrency: int = Field(default=8, ge=1, le=32)
    fx_cache_ttl_seconds: int = Field(default=3600, gt=0)
    ecb_fx_max_age_days: int = Field(default=7, ge=0)
    redis_url: str | None = Field(default=None, repr=False)
    cors_origins: str | None = None
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"  # docker/k8s: use http://alloy:4318
    otel_service_name: str = "pestoengine"
    otel_export_interval_ms: int = Field(default=60_000, gt=0)
    otel_exporter_otlp_headers: str | None = Field(default=None, repr=False)
    market_data_providers: list[ProviderId] = ["yahoo"]
    alpha_vantage_api_key: str | None = Field(default=None, repr=False)
    rate_limit_providers_per_min: int | None = None
    trusted_proxies: str | None = None
    fastapi_docs: bool = True

    @field_validator(
        "redis_url",
        "alpha_vantage_api_key",
        "otel_exporter_otlp_headers",
        "cors_origins",
        "trusted_proxies",
        mode="before",
    )
    @classmethod
    def _trim_optional(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"redis", "rediss", "unix"} or not (
                parsed.path if parsed.scheme == "unix" else parsed.hostname
            ):
                raise ValueError("REDIS_URL must be a redis, rediss or unix URL")
            _ = parsed.port
        return value

    @field_validator("otel_exporter_otlp_endpoint")
    @classmethod
    def _validate_otlp_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OTLP endpoint must be an HTTP(S) base URL")
        return value

    @field_validator("otel_service_name")
    @classmethod
    def _service_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OTEL_SERVICE_NAME cannot be empty")
        return value.strip()

    @field_validator("base_currency")
    @classmethod
    def _normalize_base_currency(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value]
        if not normalized or any(
            len(item) != 3 or not item.isascii() or not item.isalpha() for item in normalized
        ):
            raise ValueError("BASE_CURRENCY must contain three-letter currency codes")
        if len(set(normalized)) != len(normalized):
            raise ValueError("BASE_CURRENCY entries must be unique")
        return normalized

    @model_validator(mode="after")
    def _check_required_settings(self) -> "Settings":
        self.market_data_providers = list(dict.fromkeys(self.market_data_providers))
        if self.cache_backend == "redis" and self.redis_url is None:
            raise ValueError("REDIS_URL must be set when CACHE_BACKEND=redis")
        if "alphavantage" in self.market_data_providers and not self.alpha_vantage_api_key:
            raise ValueError(
                "ALPHA_VANTAGE_API_KEY required when alphavantage is in MARKET_DATA_PROVIDERS"
            )
        if not self.market_data_providers:
            raise ValueError("MARKET_DATA_PROVIDERS must contain at least one provider")
        if self.rate_limit_providers_per_min is not None and self.rate_limit_providers_per_min <= 0:
            raise ValueError(
                "RATE_LIMIT_PROVIDERS_PER_MIN must be a positive integer or left unset"
            )
        return self


@cache
def get_settings() -> Settings:
    return Settings()


request_settings: ContextVar[Settings | None] = ContextVar("request_settings", default=None)


def get_validation_settings() -> Settings:
    """Use the owning application's configuration during request validation."""
    return request_settings.get() or get_settings()
