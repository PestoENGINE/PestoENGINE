"""Unit tests for ProviderRegistry."""

from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.provider_registry import ProviderRegistry


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


def _asset(ticker: str, provider: str | None = None):
    a = MagicMock()
    a.ticker = ticker
    a.provider = provider
    return a


def _mock_provider(prices: dict) -> MagicMock:
    m = MagicMock(spec=AbstractMarketDataProvider)
    m.get_prices.return_value = prices
    return m


def _make_registry(yahoo_prices=None, av_prices=None, *, meter_provider=None):
    yahoo = _mock_provider(yahoo_prices or {})
    av = _mock_provider(av_prices or {})
    providers = {"yahoo": yahoo, "alphavantage": av}
    reg = ProviderRegistry(providers, ["yahoo", "alphavantage"], meter_provider=meter_provider)
    return reg, yahoo, av


# --- Explicit provider dispatch ---

def test_explicit_provider_routes_to_correct_provider():
    reg, yahoo, av = _make_registry(yahoo_prices={"AAPL": 150.0})
    result = reg.get_prices_for_assets([_asset("AAPL", provider="yahoo")])
    assert result == {"AAPL": 150.0}
    yahoo.get_prices.assert_called_once_with(["AAPL"])
    av.get_prices.assert_not_called()


def test_explicit_provider_batches_multiple_tickers():
    reg, yahoo, av = _make_registry(yahoo_prices={"A": 1.0, "B": 2.0})
    assets = [_asset("A", provider="yahoo"), _asset("B", provider="yahoo")]
    result = reg.get_prices_for_assets(assets)
    assert result == {"A": 1.0, "B": 2.0}
    yahoo.get_prices.assert_called_once_with(["A", "B"])


def test_explicit_unknown_provider_raises():
    reg, _, _ = _make_registry()
    with pytest.raises(MarketDataError, match="not configured"):
        reg.get_prices_for_assets([_asset("X", provider="unknown")])


def test_explicit_provider_error_wraps_with_prefix():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_prices.side_effect = MarketDataError("feed down")
    reg = ProviderRegistry({"yahoo": yahoo}, ["yahoo"])
    with pytest.raises(MarketDataError, match=r"\[yahoo\] feed down"):
        reg.get_prices_for_assets([_asset("AAPL", provider="yahoo")])


# --- Fallback chain (per-ticker) ---

def test_fallback_uses_first_provider_that_succeeds():
    reg, yahoo, av = _make_registry(yahoo_prices={"AAPL": 150.0})
    result = reg.get_prices_for_assets([_asset("AAPL")])
    assert result == {"AAPL": 150.0}
    yahoo.get_prices.assert_called_once_with(["AAPL"])
    av.get_prices.assert_not_called()


def test_fallback_falls_through_to_second_provider_on_error():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_prices.side_effect = MarketDataError("yahoo down")
    av = _mock_provider({"AAPL": 150.0})
    reg = ProviderRegistry({"yahoo": yahoo, "alphavantage": av}, ["yahoo", "alphavantage"])
    result = reg.get_prices_for_assets([_asset("AAPL")])
    assert result == {"AAPL": 150.0}
    yahoo.get_prices.assert_called_once_with(["AAPL"])
    av.get_prices.assert_called_once_with(["AAPL"])


def test_fallback_per_ticker_only_bad_ticker_goes_to_av():
    """Yahoo succeeds for A but fails for B; only B goes to AV."""
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    av = MagicMock(spec=AbstractMarketDataProvider)

    def yahoo_side_effect(tickers):
        if tickers == ["A"]:
            return {"A": 1.0}
        raise MarketDataError("no price for B")

    yahoo.get_prices.side_effect = yahoo_side_effect
    av.get_prices.return_value = {"B": 2.0}

    reg = ProviderRegistry({"yahoo": yahoo, "alphavantage": av}, ["yahoo", "alphavantage"])
    result = reg.get_prices_for_assets([_asset("A"), _asset("B")])
    assert result == {"A": 1.0, "B": 2.0}
    av.get_prices.assert_called_once_with(["B"])


def test_fallback_all_providers_fail_raises_with_ticker_name():
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_prices.side_effect = MarketDataError("down")
    av = MagicMock(spec=AbstractMarketDataProvider)
    av.get_prices.side_effect = MarketDataError("down")
    reg = ProviderRegistry({"yahoo": yahoo, "alphavantage": av}, ["yahoo", "alphavantage"])
    with pytest.raises(MarketDataError, match="'AAPL' not found"):
        reg.get_prices_for_assets([_asset("AAPL")])


# --- Mixed explicit + fallback ---

def test_mix_of_explicit_and_fallback_assets():
    yahoo = _mock_provider({"AAPL": 150.0, "MSFT": 300.0})
    av = _mock_provider({"IBM": 130.0})
    reg = ProviderRegistry({"yahoo": yahoo, "alphavantage": av}, ["yahoo", "alphavantage"])
    assets = [
        _asset("AAPL", provider="yahoo"),
        _asset("IBM", provider="alphavantage"),
        _asset("MSFT"),  # fallback — Yahoo succeeds
    ]
    result = reg.get_prices_for_assets(assets)
    assert result == {"AAPL": 150.0, "IBM": 130.0, "MSFT": 300.0}


# --- Error counter metric ---

def test_explicit_error_increments_counter_with_explicit_type():
    reader, mp = _make_otel()
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_prices.side_effect = MarketDataError("down")
    reg = ProviderRegistry({"yahoo": yahoo}, ["yahoo"], meter_provider=mp)
    with pytest.raises(MarketDataError):
        reg.get_prices_for_assets([_asset("X", provider="yahoo")])
    pts = _points(reader, "pestoengine_provider_errors_total")
    assert len(pts) == 1
    assert pts[0].attributes["error_type"] == "explicit"
    assert pts[0].attributes["provider"] == "yahoo"


def test_fallback_error_increments_counter_with_fallback_type():
    reader, mp = _make_otel()
    yahoo = MagicMock(spec=AbstractMarketDataProvider)
    yahoo.get_prices.side_effect = MarketDataError("down")
    av = _mock_provider({"X": 1.0})
    reg = ProviderRegistry({"yahoo": yahoo, "alphavantage": av}, ["yahoo", "alphavantage"], meter_provider=mp)
    reg.get_prices_for_assets([_asset("X")])
    pts = _points(reader, "pestoengine_provider_errors_total")
    assert len(pts) == 1
    assert pts[0].attributes["error_type"] == "fallback"
    assert pts[0].attributes["provider"] == "yahoo"
