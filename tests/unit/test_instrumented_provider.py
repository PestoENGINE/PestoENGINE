"""Unit tests for InstrumentedMarketDataProvider."""

import pytest
from unittest.mock import MagicMock

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.market_data.base import AbstractMarketDataProvider
from app.core.exceptions import MarketDataError


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


def test_delegates_to_underlying_provider():
    from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
    reader, mp = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = {"AAPL": 150.0, "MSFT": 300.0}
    provider = InstrumentedMarketDataProvider(mock, meter_provider=mp)

    result = provider.get_prices(["AAPL", "MSFT"])

    assert result == {"AAPL": 150.0, "MSFT": 300.0}
    mock.get_prices.assert_called_once_with(["AAPL", "MSFT"])


def test_records_duration_on_success():
    from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
    reader, mp = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = {"A": 10.0}
    provider = InstrumentedMarketDataProvider(mock, meter_provider=mp)

    provider.get_prices(["A"])

    pts = _points(reader, "pestoengine_market_fetch_duration_seconds")
    assert len(pts) == 1
    assert pts[0].sum >= 0


def test_records_duration_on_error():
    from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
    reader, mp = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.side_effect = MarketDataError("feed down")
    provider = InstrumentedMarketDataProvider(mock, meter_provider=mp)

    with pytest.raises(MarketDataError):
        provider.get_prices(["A"])

    pts = _points(reader, "pestoengine_market_fetch_duration_seconds")
    assert len(pts) == 1


def test_counter_increments_by_ticker_count_on_success():
    from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
    reader, mp = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = {"A": 1.0, "B": 2.0, "C": 3.0}
    provider = InstrumentedMarketDataProvider(mock, meter_provider=mp)

    provider.get_prices(["A", "B", "C"])

    pts = _points(reader, "pestoengine_market_fetch_total")
    assert len(pts) == 1
    assert pts[0].value == 3
    assert pts[0].attributes["outcome"] == "success"


def test_counter_increments_by_ticker_count_on_error():
    from app.market_data.instrumented_provider import InstrumentedMarketDataProvider
    reader, mp = _make_otel()
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.side_effect = MarketDataError("feed down")
    provider = InstrumentedMarketDataProvider(mock, meter_provider=mp)

    with pytest.raises(MarketDataError):
        provider.get_prices(["X", "Y"])

    pts = _points(reader, "pestoengine_market_fetch_total")
    assert len(pts) == 1
    assert pts[0].value == 2
    assert pts[0].attributes["outcome"] == "error"
