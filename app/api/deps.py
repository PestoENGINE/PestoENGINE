"""FastAPI dependency injection for shared resources."""

from functools import lru_cache
from typing import Callable

from app.core.config import Settings, get_settings
from app.fx.ecb_provider import EcbFxProvider, EcbReferenceRate
from app.market_data.base import AbstractMarketDataProvider, AbstractTickerSearchProvider
from app.market_data.cache import AbstractCache, LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider
from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
from app.market_data.provider_registry import ProviderRegistry
from app.market_data.quote import MarketQuote
from app.market_data.redis_cache import RedisCache
from app.market_data.alpha_vantage_provider import AlphaVantageProvider
from app.market_data.alpha_vantage_search_provider import AlphaVantageSearchProvider
from app.market_data.yahoo_finance_provider import YahooFinanceProvider
from app.market_data.yahoo_search_provider import YahooTickerSearchProvider
from app.rate_limit.base import AbstractRateLimitStore

PROVIDER_BUILDERS: dict[str, Callable[[Settings], AbstractMarketDataProvider]] = {
    "yahoo":        lambda s: YahooFinanceProvider(),
    "alphavantage": lambda s: AlphaVantageProvider(s.alpha_vantage_api_key),
}

SEARCH_BUILDERS: dict[str, Callable[[Settings], AbstractTickerSearchProvider]] = {
    "yahoo":        lambda s: YahooTickerSearchProvider(),
    "alphavantage": lambda s: AlphaVantageSearchProvider(s.alpha_vantage_api_key),
}


def _build_cache() -> AbstractCache[MarketQuote]:
    settings = get_settings()
    if settings.cache_backend == "redis":
        return RedisCache(
            url=settings.redis_url,  # validated by Settings
            ttl_seconds=settings.cache_ttl_seconds,
            encode=MarketQuote.to_cache_dict,
            decode=MarketQuote.from_cache_dict,
        )
    return LocalCache(ttl_seconds=settings.cache_ttl_seconds)


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
def get_fx_provider() -> EcbFxProvider:
    settings = get_settings()
    cache: AbstractCache[EcbReferenceRate]
    if settings.cache_backend == "redis":
        cache = RedisCache(
            url=settings.redis_url,  # validated by Settings
            ttl_seconds=settings.fx_cache_ttl_seconds,
            encode=EcbReferenceRate.to_cache_dict,
            decode=EcbReferenceRate.from_cache_dict,
        )
    else:
        cache = LocalCache(ttl_seconds=settings.fx_cache_ttl_seconds)
    return EcbFxProvider(
        cache,
        max_age_days=settings.ecb_fx_max_age_days,
    )


@lru_cache(maxsize=1)
def _build_search_providers() -> list[AbstractTickerSearchProvider]:
    settings = get_settings()
    return [SEARCH_BUILDERS[pid](settings) for pid in settings.market_data_providers]


def get_registry() -> ProviderRegistry:
    return _build_registry()


def get_search_providers() -> list[AbstractTickerSearchProvider]:
    return _build_search_providers()


@lru_cache(maxsize=1)
def get_rate_limit_store() -> AbstractRateLimitStore | None:
    from app.rate_limit.local_store import LocalRateLimitStore
    settings = get_settings()
    if settings.rate_limit_providers_per_min is None:
        return None
    if settings.cache_backend == "redis":
        import redis
        from app.rate_limit.redis_store import RedisRateLimitStore
        client = redis.Redis.from_url(settings.redis_url)
        return RedisRateLimitStore(client)
    return LocalRateLimitStore()
