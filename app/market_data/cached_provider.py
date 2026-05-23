"""Caching decorator for AbstractMarketDataProvider."""

import logging

from opentelemetry import metrics as _metrics
from opentelemetry import trace as _otel_trace

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
        *,
        provider_id: str,
        meter_provider: _metrics.MeterProvider | None = None,
        tracer_provider: _otel_trace.TracerProvider | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._key_prefix = f"{_KEY_PREFIX}{provider_id}:"
        backend = type(cache).__name__.removesuffix("Cache").lower()
        mp = meter_provider if meter_provider is not None else _metrics.get_meter_provider()
        meter = mp.get_meter("pestoengine.cache")
        self._cache_ops = meter.create_counter(
            "pestoengine_cache_ops_total",
            description="Cache lookup outcomes per ticker",
        )
        self._backend = backend
        self._provider_id = provider_id
        self._tracer = (
            tracer_provider.get_tracer("pestoengine.cache")
            if tracer_provider is not None
            else _otel_trace.get_tracer("pestoengine.cache")
        )

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        with self._tracer.start_as_current_span(
            "cache_lookup",
            attributes={
                "cache.backend": self._backend,
                "provider": self._provider_id,
                "tickers.count": len(tickers),
            },
        ) as span:
            prices: dict[str, float] = {}
            misses: list[str] = []
            for ticker in tickers:
                cached = self._cache.get(self._key_prefix + ticker)
                if cached is not None:
                    prices[ticker] = cached
                    self._cache_ops.add(1, {"backend": self._backend, "result": "hit"})
                else:
                    misses.append(ticker)
                    self._cache_ops.add(1, {"backend": self._backend, "result": "miss"})
            span.set_attribute("cache.hits", len(tickers) - len(misses))
            span.set_attribute("cache.misses", len(misses))
            if misses:
                fresh = self._provider.get_prices(misses)
                for ticker, price in fresh.items():
                    self._cache.set(self._key_prefix + ticker, price)
                    prices[ticker] = price
            return prices
