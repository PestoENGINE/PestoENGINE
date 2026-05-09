"""Instrumentation decorator for AbstractMarketDataProvider."""

import time

from opentelemetry import metrics as _metrics

from app.market_data.base import AbstractMarketDataProvider

FETCH_DURATION_METRIC = "pestoengine_market_fetch_duration_seconds"


class InstrumentedMarketDataProvider(AbstractMarketDataProvider):
    """Decorator that records fetch duration and outcomes for any provider.

    Positioned inside CachedMarketDataProvider, so only cache misses
    (real API calls) are measured.
    """

    def __init__(
        self,
        provider: AbstractMarketDataProvider,
        *,
        provider_id: str,
        meter_provider: _metrics.MeterProvider | None = None,
    ) -> None:
        self._provider = provider
        self._provider_id = provider_id
        mp = meter_provider if meter_provider is not None else _metrics.get_meter_provider()
        meter = mp.get_meter("pestoengine.market_data")
        self._fetch_duration = meter.create_histogram(
            FETCH_DURATION_METRIC,
            description="Market data API fetch duration (cache misses only)",
            unit="s",
        )
        self._fetch_total = meter.create_counter(
            "pestoengine_market_fetch_total",
            description="Tickers fetched from market data API",
        )

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        start = time.perf_counter()
        outcome = "success"
        try:
            result = self._provider.get_prices(tickers)
            return result
        except Exception:
            outcome = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            self._fetch_duration.record(elapsed, {"provider": self._provider_id})
            self._fetch_total.add(len(tickers), {"outcome": outcome, "provider": self._provider_id})
