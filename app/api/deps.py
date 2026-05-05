"""FastAPI dependency injection for shared resources.

Emergency fallback procedure (if Yahoo Finance API breaks):

  PRICE PROVIDER
    Step 1: requirements.txt  -> uncomment yfinance and pandas
    Step 2: this file         -> swap the import below:
              active:   from app.market_data.yahoo_finance_provider import YahooFinanceProvider
              fallback: from app.market_data.yfinance_provider import YFinanceProvider
            and replace YahooFinanceProvider() with YFinanceProvider() in _build_provider()
    Step 3: rebuild Docker image

  SEARCH PROVIDER
    Step 1: requirements.txt           -> uncomment yfinance
    Step 2: yahoo_search_provider.py   -> comment out the httpx class,
                                          uncomment the yfinance class (same class name, no import change here)
    Step 3: rebuild Docker image
"""

from functools import lru_cache

from app.core.config import get_settings
from app.market_data.base import AbstractMarketDataProvider, AbstractTickerSearchProvider
from app.market_data.cache import AbstractCache, LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider
from app.market_data.yahoo_finance_provider import YahooFinanceProvider
from app.market_data.yahoo_search_provider import YahooTickerSearchProvider


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
def _build_provider() -> AbstractMarketDataProvider:
    return CachedMarketDataProvider(YahooFinanceProvider(), _build_cache())


def get_market_provider() -> AbstractMarketDataProvider:
    return _build_provider()


@lru_cache(maxsize=1)
def _build_search_provider() -> AbstractTickerSearchProvider:
    return YahooTickerSearchProvider()


def get_ticker_search_provider() -> AbstractTickerSearchProvider:
    return _build_search_provider()
