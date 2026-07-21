"""Unit tests for ProviderRegistry."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.provider_registry import ProviderRegistry
from tests.helpers import make_quotes


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


def _asset(ticker: str, provider: str | None = None, currency: str | None = None):
    return SimpleNamespace(ticker=ticker, provider=provider, currency=currency)


def _mock_provider(prices: dict, *, currency: str = "EUR") -> MagicMock:
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_quotes.return_value = make_quotes(prices, currency=currency)
    return mock


def _make_registry(yahoo_prices=None, av_prices=None, *, meter_provider=None):
    yahoo = _mock_provider(yahoo_prices or {})
    alpha = _mock_provider(av_prices or {})
    registry = ProviderRegistry(
        {"yahoo": yahoo, "alphavantage": alpha},
        ["yahoo", "alphavantage"],
        meter_provider=meter_provider,
    )
    return registry, yahoo, alpha


def test_explicit_provider_routes_to_correct_provider():
    registry, yahoo, alpha = _make_registry(yahoo_prices={"AAPL": 150})
    result = registry.get_quotes_for_assets([_asset("AAPL", provider="yahoo")])
    assert result["AAPL"].price == 150
    yahoo.get_quotes.assert_called_once_with(["AAPL"], currency_hints={})
    alpha.get_quotes.assert_not_called()


def test_explicit_provider_batches_tickers_and_currency_hints():
    registry, yahoo, _ = _make_registry(yahoo_prices={"A": 1, "B": 2})
    assets = [
        _asset("A", provider="yahoo", currency="EUR"),
        _asset("B", provider="yahoo"),
    ]
    assert set(registry.get_quotes_for_assets(assets)) == {"A", "B"}
    yahoo.get_quotes.assert_called_once_with(
        ["A", "B"], currency_hints={"A": "EUR"},
    )


def test_explicit_unknown_provider_raises():
    registry, _, _ = _make_registry()
    with pytest.raises(MarketDataError, match="not configured"):
        registry.get_quotes_for_assets([_asset("X", provider="unknown")])


def test_explicit_provider_error_wraps_with_prefix():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_quotes.side_effect = MarketDataError("feed down")
    registry = ProviderRegistry({"yahoo": yahoo}, ["yahoo"])
    with pytest.raises(MarketDataError, match=r"\[yahoo\] feed down"):
        registry.get_quotes_for_assets([_asset("AAPL", provider="yahoo")])


def test_fallback_uses_first_provider_that_succeeds():
    registry, yahoo, alpha = _make_registry(yahoo_prices={"AAPL": 150})
    assert registry.get_quotes_for_assets([_asset("AAPL")])["AAPL"].price == 150
    yahoo.get_quotes.assert_called_once_with(["AAPL"], currency_hints={})
    alpha.get_quotes.assert_not_called()


def test_fallback_falls_through_and_forwards_currency_hint():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_quotes.side_effect = MarketDataError("yahoo down")
    alpha = _mock_provider({"AAPL": 150}, currency="USD")
    registry = ProviderRegistry(
        {"yahoo": yahoo, "alphavantage": alpha}, ["yahoo", "alphavantage"],
    )
    result = registry.get_quotes_for_assets([_asset("AAPL", currency="USD")])
    assert result["AAPL"].price == 150
    for provider in (yahoo, alpha):
        provider.get_quotes.assert_called_once_with(
            ["AAPL"], currency_hints={"AAPL": "USD"},
        )


def test_fallback_is_resolved_per_ticker():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    alpha = _mock_provider({"B": 2})

    def yahoo_side_effect(tickers, *, currency_hints=None):
        if tickers == ["A"]:
            return make_quotes({"A": 1})
        raise MarketDataError("no quote for B")

    yahoo.get_quotes.side_effect = yahoo_side_effect
    registry = ProviderRegistry(
        {"yahoo": yahoo, "alphavantage": alpha}, ["yahoo", "alphavantage"],
    )
    assert set(registry.get_quotes_for_assets([_asset("A"), _asset("B")])) == {"A", "B"}
    alpha.get_quotes.assert_called_once_with(["B"], currency_hints={})


def test_fallback_all_providers_fail_raises_with_ticker_name():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_quotes.side_effect = MarketDataError("down")
    alpha = MagicMock(spec=AbstractMarketDataProvider)
    alpha.get_quotes.side_effect = MarketDataError("down")
    registry = ProviderRegistry(
        {"yahoo": yahoo, "alphavantage": alpha}, ["yahoo", "alphavantage"],
    )
    with pytest.raises(MarketDataError, match="'AAPL' not found"):
        registry.get_quotes_for_assets([_asset("AAPL")])


def test_mix_of_explicit_and_fallback_assets():
    yahoo = _mock_provider({"AAPL": 150, "MSFT": 300})
    alpha = _mock_provider({"IBM": 130}, currency="USD")
    registry = ProviderRegistry(
        {"yahoo": yahoo, "alphavantage": alpha}, ["yahoo", "alphavantage"],
    )
    assets = [
        _asset("AAPL", provider="yahoo"),
        _asset("IBM", provider="alphavantage", currency="USD"),
        _asset("MSFT"),
    ]
    assert set(registry.get_quotes_for_assets(assets)) == {"AAPL", "IBM", "MSFT"}


def test_explicit_error_increments_counter_with_explicit_type():
    reader, meter = _make_otel()
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_quotes.side_effect = MarketDataError("down")
    registry = ProviderRegistry({"yahoo": yahoo}, ["yahoo"], meter_provider=meter)
    with pytest.raises(MarketDataError):
        registry.get_quotes_for_assets([_asset("X", provider="yahoo")])
    point = _points(reader, "pestoengine_provider_errors_total")[0]
    assert point.attributes["error_type"] == "explicit"
    assert point.attributes["provider"] == "yahoo"


def test_fallback_error_increments_counter_with_fallback_type():
    reader, meter = _make_otel()
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_quotes.side_effect = MarketDataError("down")
    alpha = _mock_provider({"X": 1})
    registry = ProviderRegistry(
        {"yahoo": yahoo, "alphavantage": alpha},
        ["yahoo", "alphavantage"],
        meter_provider=meter,
    )
    registry.get_quotes_for_assets([_asset("X", currency="EUR")])
    point = _points(reader, "pestoengine_provider_errors_total")[0]
    assert point.attributes["error_type"] == "fallback"
    assert point.attributes["provider"] == "yahoo"
