"""Caching decorator for AbstractMarketDataProvider."""

import logging

from opentelemetry import metrics as _metrics
from opentelemetry import trace as _otel_trace

from app.market_data.base import AbstractMarketDataProvider
from app.market_data.cache import AbstractCache
from app.market_data.quote import MarketQuote

logger = logging.getLogger(__name__)

_KEY_PREFIX = "market:quote:v2:"


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
        cache: AbstractCache[MarketQuote],
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

    def get_quotes(
        self,
        tickers: list[str],
        *,
        currency_hints: dict[str, str] | None = None,
    ) -> dict[str, MarketQuote]:
        hints = currency_hints or {}
        with self._tracer.start_as_current_span(
            "cache_lookup",
            attributes={
                "cache.backend": self._backend,
                "provider": self._provider_id,
                "tickers.count": len(tickers),
            },
        ) as span:
            quotes: dict[str, MarketQuote] = {}
            misses: list[str] = []
            for ticker in tickers:
                hint = hints.get(ticker)
                cache_key = self._key_prefix + ticker + ":" + (hint or "_")
                cached = self._cache.get(cache_key)
                if cached is not None:
                    quotes[ticker] = cached
                    self._cache_ops.add(1, {"backend": self._backend, "result": "hit"})
                else:
                    misses.append(ticker)
                    self._cache_ops.add(1, {"backend": self._backend, "result": "miss"})
            span.set_attribute("cache.hits", len(tickers) - len(misses))
            span.set_attribute("cache.misses", len(misses))
            if misses:
                fresh = self._provider.get_quotes(
                    misses,
                    currency_hints={
                        ticker: hints[ticker]
                        for ticker in misses
                        if ticker in hints
                    },
                )
                for ticker, quote in fresh.items():
                    hint = hints.get(ticker)
                    cache_key = self._key_prefix + ticker + ":" + (hint or "_")
                    self._cache.set(cache_key, quote)
                    quotes[ticker] = quote
            return quotes
