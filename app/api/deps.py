"""FastAPI dependency injection for shared resources."""

from functools import lru_cache
from typing import Callable

from app.core.config import Settings, get_settings
from app.market_data.base import AbstractMarketDataProvider, AbstractTickerSearchProvider
from app.market_data.cache import AbstractCache, LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider
from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
from app.market_data.provider_registry import ProviderRegistry
from app.market_data.alpha_vantage_provider import AlphaVantageProvider
from app.market_data.alpha_vantage_search_provider import AlphaVantageSearchProvider
from app.market_data.yahoo_finance_provider import YahooFinanceProvider
from app.market_data.yahoo_search_provider import YahooTickerSearchProvider

PROVIDER_BUILDERS: dict[str, Callable[[Settings], AbstractMarketDataProvider]] = {
    "yahoo":        lambda s: YahooFinanceProvider(),
    "alphavantage": lambda s: AlphaVantageProvider(s.alpha_vantage_api_key),
}

SEARCH_BUILDERS: dict[str, Callable[[Settings], AbstractTickerSearchProvider]] = {
    "yahoo":        lambda s: YahooTickerSearchProvider(),
    "alphavantage": lambda s: AlphaVantageSearchProvider(s.alpha_vantage_api_key),
}


@lru_cache(maxsize=1)
def _build_cache() -> AbstractCache:
    s = get_settings()
    if s.cache_backend == "redis":
        if not s.redis_url:
            raise ValueError(
                "REDIS_URL must be set when CACHE_BACKEND=redis. "
                "Pass it as an environment variable."
            )
        from app.market_data.redis_cache import RedisCache
        return RedisCache(url=s.redis_url, ttl_seconds=s.cache_ttl_seconds)
    return LocalCache(ttl_seconds=s.cache_ttl_seconds)


@lru_cache(maxsize=1)
def _build_registry() -> ProviderRegistry:
    settings = get_settings()
    cache = _build_cache()
    chains: dict[str, AbstractMarketDataProvider] = {}
    for pid in settings.market_data_providers:
        raw = PROVIDER_BUILDERS[pid](settings)
        chains[pid] = CachedMarketDataProvider(
            InstrumentedMarketDataProvider(raw, provider_id=pid),
            cache,
            provider_id=pid,
        )
    return ProviderRegistry(chains, list(settings.market_data_providers))


@lru_cache(maxsize=1)
def _build_search_providers() -> list[AbstractTickerSearchProvider]:
    settings = get_settings()
    return [SEARCH_BUILDERS[pid](settings) for pid in settings.market_data_providers]


def get_registry() -> ProviderRegistry:
    return _build_registry()


def get_search_providers() -> list[AbstractTickerSearchProvider]:
    return _build_search_providers()
