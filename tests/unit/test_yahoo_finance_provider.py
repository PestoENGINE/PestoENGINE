"""Unit tests for YahooFinanceProvider (httpx-based)."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import MarketDataError
from app.market_data.yahoo_finance_provider import YahooFinanceProvider


def _resp(
    closes: list,
    *,
    currency: str | None = "USD",
) -> MagicMock:
    """Build a mock httpx response with the given close values."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": currency},
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }
    return m


@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_single_ticker_returns_last_close(mock_get):
    mock_get.return_value = _resp([100.0, 101.5, 102.0])
    provider = YahooFinanceProvider()
    result = provider.get_quotes(["AAPL"])
    quote = result["AAPL"]
    assert quote.price == Decimal("102.0")
    assert quote.currency == "USD"
    mock_get.return_value.json.assert_called_once_with(parse_float=Decimal)


@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_multi_ticker_calls_each_url(mock_get):
    mock_get.side_effect = [
        _resp([50.0]),
        _resp([75.0]),
    ]
    provider = YahooFinanceProvider()
    result = provider.get_quotes(["A", "B"])
    assert result["A"].price == Decimal("50.0")
    assert result["B"].price == Decimal("75.0")
    assert mock_get.call_count == 2


@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_none_values_in_close_are_filtered(mock_get):
    mock_get.return_value = _resp([None, 99.0, None])
    provider = YahooFinanceProvider()
    result = provider.get_quotes(["X"])
    assert result["X"].price == Decimal("99.0")


@patch("app.market_data.yahoo_finance_provider.time.sleep")
@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_raises_market_data_error_after_all_retries_fail(mock_get, mock_sleep):
    mock_get.side_effect = RuntimeError("connection refused")
    provider = YahooFinanceProvider()
    with pytest.raises(MarketDataError, match="after 3 attempts"):
        provider.get_quotes(["FAIL"])
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


@patch("app.market_data.yahoo_finance_provider.time.sleep")
@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_succeeds_on_second_attempt(mock_get, mock_sleep):
    mock_get.side_effect = [RuntimeError("timeout"), _resp([42.0])]
    provider = YahooFinanceProvider()
    result = provider.get_quotes(["Z"])
    assert result["Z"].price == Decimal("42.0")
    mock_sleep.assert_called_once()


@patch("app.market_data.yahoo_finance_provider.time.sleep")
@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_empty_close_after_filtering_retries_and_raises(mock_get, mock_sleep):
    mock_get.return_value = _resp([None, None])
    provider = YahooFinanceProvider()
    with pytest.raises(MarketDataError, match="after 3 attempts"):
        provider.get_quotes(["EMPTY"])
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


def test_empty_ticker_list_raises_value_error():
    provider = YahooFinanceProvider()
    with pytest.raises(ValueError, match="empty"):
        provider.get_quotes([])


@patch("app.market_data.yahoo_finance_provider.time.sleep")
@patch("app.market_data.yahoo_finance_provider.httpx.get")
def test_missing_currency_is_not_invented(mock_get, mock_sleep):
    mock_get.return_value = _resp([10], currency=None)

    with pytest.raises(MarketDataError, match="Currency missing"):
        YahooFinanceProvider().get_quotes(["UNKNOWN"])

    assert mock_get.call_count == 3
