"""Metrics tests for CachedMarketDataProvider."""

from unittest.mock import MagicMock

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.market_data.base import AbstractMarketDataProvider
from app.market_data.cache import LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider, _KEY_PREFIX
from tests.helpers import make_quote, make_quotes

_TEST_KEY_PREFIX = _KEY_PREFIX + "test:"


def _make_otel():
    reader = InMemoryMetricReader()
    return reader, MeterProvider(metric_readers=[reader])


def _points(reader, name):
    data = reader.get_metrics_data()
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                if metric.name == name:
                    return list(metric.data.data_points)
    return []


def _key(ticker: str) -> str:
    return _TEST_KEY_PREFIX + ticker + ":_"


def _make_provider(prices, *, meter_provider=None):
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_quotes.return_value = make_quotes(prices)
    cache = LocalCache(ttl_seconds=300)
    return (
        CachedMarketDataProvider(
            mock, cache, provider_id="test", meter_provider=meter_provider,
        ),
        cache,
    )


def _count(points, outcome):
    return sum(p.value for p in points if p.attributes.get("result") == outcome)


def test_cache_miss_recorded_per_ticker():
    reader, meter = _make_otel()
    provider, _ = _make_provider({"A": 1, "B": 2}, meter_provider=meter)
    provider.get_quotes(["A", "B"])
    assert _count(_points(reader, "pestoengine_cache_ops_total"), "miss") == 2


def test_cache_hit_recorded_per_ticker():
    reader, meter = _make_otel()
    provider, cache = _make_provider({}, meter_provider=meter)
    cache.set(_key("A"), make_quote(10))
    cache.set(_key("B"), make_quote(20))
    provider.get_quotes(["A", "B"])
    assert _count(_points(reader, "pestoengine_cache_ops_total"), "hit") == 2


def test_backend_label_is_local_for_local_cache():
    reader, meter = _make_otel()
    provider, _ = _make_provider({"A": 1}, meter_provider=meter)
    provider.get_quotes(["A"])
    points = _points(reader, "pestoengine_cache_ops_total")
    assert all(p.attributes.get("backend") == "local" for p in points)


def test_partial_hit_counts_correctly():
    reader, meter = _make_otel()
    provider, cache = _make_provider({"B": 2}, meter_provider=meter)
    cache.set(_key("A"), make_quote(1))
    provider.get_quotes(["A", "B"])
    points = _points(reader, "pestoengine_cache_ops_total")
    assert (_count(points, "hit"), _count(points, "miss")) == (1, 1)


def test_cache_lookup_creates_span_with_hit_miss_counts():
    exporter = InMemorySpanExporter()
    tracer = SdkTracerProvider()
    tracer.add_span_processor(SimpleSpanProcessor(exporter))
    _, meter = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_quotes.return_value = make_quotes({"B": 2})
    cache = LocalCache(ttl_seconds=300)
    provider = CachedMarketDataProvider(
        mock, cache, provider_id="test", meter_provider=meter, tracer_provider=tracer,
    )
    cache.set(_key("A"), make_quote(1))
    provider.get_quotes(["A", "B"])
    span = next(s for s in exporter.get_finished_spans() if s.name == "cache_lookup")
    assert (span.attributes["cache.hits"], span.attributes["cache.misses"]) == (1, 1)
    tracer.shutdown()
