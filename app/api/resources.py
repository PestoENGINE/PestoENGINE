"""Resources owned and closed by one application lifespan."""

import asyncio
from contextlib import ExitStack

import httpx

from app.core.config import Settings
from app.core.redis_client import create_redis_client
from app.core.telemetry import setup_telemetry
from app.fx.ecb_provider import EcbFxProvider, EcbReferenceRate
from app.market_data.alpha_vantage_provider import AlphaVantageProvider
from app.market_data.alpha_vantage_search_provider import AlphaVantageSearchProvider
from app.market_data.cache import AbstractCache, LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider
from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
from app.market_data.provider_registry import ProviderRegistry
from app.market_data.quote import MarketQuote
from app.market_data.redis_cache import RedisCache
from app.market_data.yahoo_finance_provider import YahooFinanceProvider
from app.market_data.yahoo_search_provider import YahooTickerSearchProvider
from app.rate_limit.local_store import LocalRateLimitStore
from app.rate_limit.redis_store import RedisRateLimitStore


class AppResources:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stack = ExitStack()
        self.semaphore = asyncio.Semaphore(settings.provider_concurrency)
        self.pending_work: set[asyncio.Future] = set()
        self.meter_provider = self.tracer_provider = self.logger_provider = None
        try:
            if settings.otel_enabled:
                self.meter_provider, self.tracer_provider, self.logger_provider = setup_telemetry(
                    settings.otel_service_name,
                    settings.otel_exporter_otlp_endpoint,
                    settings.otel_export_interval_ms,
                    settings.otel_exporter_otlp_headers,
                    register_global=False,
                )
                for provider in (self.meter_provider, self.tracer_provider, self.logger_provider):
                    self._stack.callback(provider.shutdown)
            self.client = self._stack.enter_context(
                httpx.Client(
                    limits=httpx.Limits(
                        max_connections=settings.provider_concurrency,
                        max_keepalive_connections=settings.provider_concurrency,
                    )
                )
            )
            self.redis_client = None
            if settings.cache_backend == "redis":
                self.redis_client = create_redis_client(
                    settings.redis_url, settings.redis_timeout_seconds
                )
                self._stack.callback(self.redis_client.close)

            quote_cache = self._cache(settings.cache_ttl_seconds, MarketQuote)
            fx_cache = self._cache(settings.fx_cache_ttl_seconds, EcbReferenceRate)
            telemetry = {
                "meter_provider": self.meter_provider,
                "tracer_provider": self.tracer_provider,
            }
            price_options = {
                "client": self.client,
                "timeout": settings.provider_timeout_seconds,
                "max_age_days": settings.quote_max_age_days,
            }
            search_options = {"client": self.client, "timeout": settings.provider_timeout_seconds}
            chains = {}
            self.search_providers = []
            for pid in settings.market_data_providers:
                if pid == "yahoo":
                    provider = YahooFinanceProvider(**price_options)
                    search = YahooTickerSearchProvider(**search_options)
                else:
                    provider = AlphaVantageProvider(settings.alpha_vantage_api_key, **price_options)
                    search = AlphaVantageSearchProvider(
                        settings.alpha_vantage_api_key, **search_options
                    )
                chains[pid] = CachedMarketDataProvider(
                    InstrumentedMarketDataProvider(provider, provider_id=pid, **telemetry),
                    quote_cache,
                    provider_id=pid,
                    max_age_days=settings.quote_max_age_days,
                    **telemetry,
                )
                self.search_providers.append(search)
            self.registry = ProviderRegistry(
                chains, list(settings.market_data_providers), meter_provider=self.meter_provider
            )
            self.fx_provider = EcbFxProvider(
                fx_cache,
                max_age_days=settings.ecb_fx_max_age_days,
                client=self.client,
                timeout=settings.provider_timeout_seconds,
            )
            self.rate_limit_store = None
            if settings.rate_limit_providers_per_min is not None:
                self.rate_limit_store = (
                    RedisRateLimitStore(self.redis_client)
                    if self.redis_client is not None
                    else LocalRateLimitStore(max_entries=settings.local_cache_max_entries)
                )
        except BaseException:
            self._stack.close()
            raise

    def _cache(self, ttl: int, value_type: type) -> AbstractCache:
        if self.redis_client is not None:
            return RedisCache(
                self.settings.redis_url,
                ttl,
                encode=value_type.to_cache_dict,
                decode=value_type.from_cache_dict,
                client=self.redis_client,
            )
        return LocalCache(ttl, max_entries=self.settings.local_cache_max_entries)

    def close(self) -> None:
        self._stack.close()
