"""Unit tests for run_rebalance() metric recording."""

import app.services.rebalance_service as _svc
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.market_data.base import AbstractMarketDataProvider
from app.schemas.request import AssetIn, RebalanceRequest


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
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = {f"T{i}": 10.0 for i in range(len(request.assets))}
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
