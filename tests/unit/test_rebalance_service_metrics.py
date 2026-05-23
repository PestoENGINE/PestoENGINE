"""Unit tests for run_rebalance() metric recording."""

import app.services.rebalance_service as _svc
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.market_data.provider_registry import ProviderRegistry
from app.schemas.request import AssetIn, RebalanceRequest
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


def _simple_request(n_assets: int = 2, optimal: bool = False) -> RebalanceRequest:
    pct = 100.0 / n_assets
    return RebalanceRequest(
        only_buy=True,
        increment=1000.0,
        optimal_redistribute=optimal,
        assets=[
            AssetIn(ticker=f"T{i}", desired_percentage=pct, shares=0.0, fees=0.0)
            for i in range(n_assets)
        ],
    )


def _run(request, mp):
    mock = MagicMock(spec=ProviderRegistry)
    mock.get_prices_for_assets.return_value = {f"T{i}": 10.0 for i in range(len(request.assets))}
    return _svc.run_rebalance(request, mock, meter_provider=mp)


@pytest.fixture(autouse=True)
def reset_instruments():
    _svc._rebalance_instruments.cache_clear()
    yield
    _svc._rebalance_instruments.cache_clear()


def test_duration_recorded_on_success():
    reader, mp = _make_otel()

    _run(_simple_request(), mp)

    pts = _points(reader, "pestoengine_rebalance_duration_seconds")
    assert len(pts) == 1
    assert pts[0].sum >= 0


def test_ticker_count_recorded():
    reader, mp = _make_otel()

    _run(_simple_request(n_assets=3), mp)

    pts = _points(reader, "pestoengine_rebalance_tickers")
    assert len(pts) == 1
    assert pts[0].sum == 3


def test_algorithm_label_greedy():
    reader, mp = _make_otel()

    _run(_simple_request(optimal=False), mp)

    pts = _points(reader, "pestoengine_rebalance_duration_seconds")
    assert pts[0].attributes["algorithm"] == "greedy"


def test_algorithm_label_dp():
    reader, mp = _make_otel()

    _run(_simple_request(optimal=True), mp)

    pts = _points(reader, "pestoengine_rebalance_duration_seconds")
    assert pts[0].attributes["algorithm"] == "dp"


def test_rebalance_compute_creates_span_with_attributes():
    exporter = InMemorySpanExporter()
    tp = SdkTracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(exporter))
    reader, mp = _make_otel()
    mock = MagicMock(spec=ProviderRegistry)
    mock.get_prices_for_assets.return_value = {"T0": 10.0, "T1": 10.0}
    _svc.run_rebalance(
        _simple_request(optimal=False),
        mock,
        meter_provider=mp,
        tracer_provider=tp,
    )
    spans = exporter.get_finished_spans()
    span = next(s for s in spans if s.name == "rebalance_compute")
    assert span.attributes["rebalance.algorithm"] == "greedy"
    assert span.attributes["rebalance.tickers.count"] == 2
    tp.shutdown()
