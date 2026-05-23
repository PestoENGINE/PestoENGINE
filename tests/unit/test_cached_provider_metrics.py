"""Unit tests for CachedMarketDataProvider metric recording."""

from unittest.mock import MagicMock

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.market_data.base import AbstractMarketDataProvider
from app.market_data.cache import LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider, _KEY_PREFIX
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _make_otel():
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return reader, provider


def _points(reader, name):
    data = reader.get_metrics_data()
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == name:
                    return list(m.data.data_points)
    return []


_TEST_KEY_PREFIX = _KEY_PREFIX + "test:"


def _make_provider(prices, *, meter_provider=None):
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = prices
    cache = LocalCache(ttl_seconds=300)
    return CachedMarketDataProvider(mock, cache, provider_id="test", meter_provider=meter_provider), mock, cache


def test_cache_miss_recorded_per_ticker():
    reader, mp = _make_otel()
    provider, _, _ = _make_provider({"A": 1.0, "B": 2.0}, meter_provider=mp)

    provider.get_prices(["A", "B"])

    pts = _points(reader, "pestoengine_cache_ops_total")
    miss_pts = [p for p in pts if p.attributes.get("result") == "miss"]
    assert sum(p.value for p in miss_pts) == 2


def test_cache_hit_recorded_per_ticker():
    reader, mp = _make_otel()
    provider, _, cache = _make_provider({}, meter_provider=mp)
    cache.set(_TEST_KEY_PREFIX + "A", 10.0)
    cache.set(_TEST_KEY_PREFIX + "B", 20.0)

    provider.get_prices(["A", "B"])

    pts = _points(reader, "pestoengine_cache_ops_total")
    hit_pts = [p for p in pts if p.attributes.get("result") == "hit"]
    assert sum(p.value for p in hit_pts) == 2


def test_backend_label_is_local_for_local_cache():
    reader, mp = _make_otel()
    provider, _, _ = _make_provider({"A": 1.0}, meter_provider=mp)

    provider.get_prices(["A"])

    pts = _points(reader, "pestoengine_cache_ops_total")
    assert all(p.attributes.get("backend") == "local" for p in pts)


def test_partial_hit_counts_correctly():
    reader, mp = _make_otel()
    provider, _, cache = _make_provider({"B": 2.0}, meter_provider=mp)
    cache.set(_TEST_KEY_PREFIX + "A", 1.0)

    provider.get_prices(["A", "B"])

    pts = _points(reader, "pestoengine_cache_ops_total")
    hits = sum(p.value for p in pts if p.attributes.get("result") == "hit")
    misses = sum(p.value for p in pts if p.attributes.get("result") == "miss")
    assert hits == 1
    assert misses == 1


def test_cache_lookup_creates_span_with_hit_miss_counts():
    exporter = InMemorySpanExporter()
    tp = SdkTracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(exporter))
    _, mp = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = {"B": 2.0}
    cache = LocalCache(ttl_seconds=300)
    provider = CachedMarketDataProvider(
        mock, cache, provider_id="test", meter_provider=mp, tracer_provider=tp
    )
    cache.set(_TEST_KEY_PREFIX + "A", 1.0)
    provider.get_prices(["A", "B"])
    spans = exporter.get_finished_spans()
    span = next(s for s in spans if s.name == "cache_lookup")
    assert span.attributes["cache.hits"] == 1
    assert span.attributes["cache.misses"] == 1
    tp.shutdown()
