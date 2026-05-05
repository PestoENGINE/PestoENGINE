"""Caching decorator for AbstractMarketDataProvider."""

import logging

from app.market_data.base import AbstractMarketDataProvider
from app.market_data.cache import AbstractCache

logger = logging.getLogger(__name__)

_KEY_PREFIX = "market:price:"


class CachedMarketDataProvider(AbstractMarketDataProvider):
    """Decorator that adds a cache layer to any AbstractMarketDataProvider.

    Semantica fail-fast: if one or more tickers are not in cache and the
    underlying provider raises, the exception propagates in full. A rebalance
    calculation requires all prices - a partial result would be silently wrong.

    Stale data is never returned. If resilience is needed in the future, add
    an explicit ``stale_on_error`` flag rather than changing the default.
    """

    def __init__(
        self,
        provider: AbstractMarketDataProvider,
        cache: AbstractCache,
    ) -> None:
        self._provider = provider
        self._cache = cache

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        misses: list[str] = []

        for ticker in tickers:
            cached = self._cache.get(_KEY_PREFIX + ticker)
            if cached is not None:
                logger.debug("Cache HIT for %s", ticker)
                prices[ticker] = cached
            else:
                logger.debug("Cache MISS for %s", ticker)
                misses.append(ticker)

        if misses:
            fresh = self._provider.get_prices(misses)
            for ticker, price in fresh.items():
                self._cache.set(_KEY_PREFIX + ticker, price)
                prices[ticker] = price

        return prices
