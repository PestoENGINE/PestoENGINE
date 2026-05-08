"""Unit tests for AlphaVantageProvider."""

from unittest.mock import MagicMock, patch

import pytest
import httpx

from app.market_data.alpha_vantage_provider import AlphaVantageProvider
from app.core.exceptions import MarketDataError


def _resp(body: dict, status_code: int = 200) -> MagicMock:
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = body
    m.status_code = status_code
    return m


def test_raises_on_empty_api_key():
    with pytest.raises(ValueError, match="non-empty api_key"):
        AlphaVantageProvider("")


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_returns_price_on_success(mock_get):
    mock_get.return_value = _resp({"Global Quote": {"01. symbol": "IBM", "05. price": "134.56"}})
    provider = AlphaVantageProvider("key")
    result = provider.get_prices(["IBM"])
    assert result == {"IBM": 134.56}


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_fetches_multiple_tickers(mock_get):
    mock_get.side_effect = [
        _resp({"Global Quote": {"05. price": "100.0"}}),
        _resp({"Global Quote": {"05. price": "200.0"}}),
    ]
    provider = AlphaVantageProvider("key")
    result = provider.get_prices(["A", "B"])
    assert result == {"A": 100.0, "B": 200.0}
    assert mock_get.call_count == 2


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_rate_limit_note_raises_immediately(mock_get):
    mock_get.return_value = _resp({"Note": "Thank you for using Alpha Vantage. Our API call frequency..."})
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="rate limit"):
        provider.get_prices(["AAPL"])
    assert mock_get.call_count == 1


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_rate_limit_information_raises_immediately(mock_get):
    mock_get.return_value = _resp({"Information": "The **demo** API key..."})
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="rate limit"):
        provider.get_prices(["AAPL"])
    assert mock_get.call_count == 1


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_empty_global_quote_raises(mock_get):
    mock_get.return_value = _resp({"Global Quote": {}})
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="No price returned"):
        provider.get_prices(["UNKNOWN"])


@patch("app.market_data.alpha_vantage_provider.time.sleep")
@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_http_error_retries_then_raises(mock_get, mock_sleep):
    mock_get.side_effect = httpx.HTTPError("timeout")
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="3 attempts"):
        provider.get_prices(["AAPL"])
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
