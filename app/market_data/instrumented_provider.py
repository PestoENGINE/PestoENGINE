"""Instrumentation decorator for AbstractMarketDataProvider."""

import time

from opentelemetry import metrics as _metrics
from opentelemetry import trace as _otel_trace

from app.market_data.base import AbstractMarketDataProvider
from app.market_data.quote import MarketQuote

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
        tracer_provider: _otel_trace.TracerProvider | None = None,
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
        self._tracer = (
            tracer_provider.get_tracer("pestoengine.market_data")
            if tracer_provider is not None
            else _otel_trace.get_tracer("pestoengine.market_data")
        )

    def get_quotes(
        self,
        tickers: list[str],
        *,
        currency_hints: dict[str, str] | None = None,
    ) -> dict[str, MarketQuote]:
        start = time.perf_counter()
        outcome = "success"
        with self._tracer.start_as_current_span(
            "market_fetch",
            attributes={
                "provider": self._provider_id,
                "tickers.count": len(tickers),
            },
        ) as span:
            try:
                return self._provider.get_quotes(
                    tickers,
                    currency_hints=currency_hints,
                )
            except Exception as exc:
                outcome = "error"
                span.set_status(_otel_trace.Status(_otel_trace.StatusCode.ERROR))
                span.record_exception(exc)
                raise
            finally:
                elapsed = time.perf_counter() - start
                self._fetch_duration.record(elapsed, {"provider": self._provider_id})
                self._fetch_total.add(len(tickers), {"outcome": outcome, "provider": self._provider_id})
