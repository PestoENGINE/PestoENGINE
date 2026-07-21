"""Unit tests for AlphaVantageProvider."""

from unittest.mock import MagicMock, patch
from decimal import Decimal

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
    mock_get.return_value = _resp({
        "Global Quote": {
            "01. symbol": "IBM",
            "05. price": "134.5600",
        }
    })
    provider = AlphaVantageProvider("key")
    result = provider.get_quotes(["IBM"], currency_hints={"IBM": "USD"})
    quote = result["IBM"]
    assert quote.price == Decimal("134.5600")
    assert quote.currency == "USD"


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_fetches_multiple_tickers(mock_get):
    mock_get.side_effect = [
        _resp({"Global Quote": {"05. price": "100.0"}}),
        _resp({"Global Quote": {"05. price": "200.0"}}),
    ]
    provider = AlphaVantageProvider("key")
    result = provider.get_quotes(
        ["A", "B"],
        currency_hints={"A": "EUR", "B": "EUR"},
    )
    assert result["A"].price == Decimal("100.0")
    assert result["B"].price == Decimal("200.0")
    assert mock_get.call_count == 2


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_rate_limit_note_raises_immediately(mock_get):
    mock_get.return_value = _resp({"Note": "Thank you for using Alpha Vantage. Our API call frequency..."})
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="rate limit"):
        provider.get_quotes(["AAPL"], currency_hints={"AAPL": "USD"})
    assert mock_get.call_count == 1


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_rate_limit_information_raises_immediately(mock_get):
    mock_get.return_value = _resp({"Information": "The **demo** API key..."})
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="rate limit"):
        provider.get_quotes(["AAPL"], currency_hints={"AAPL": "USD"})
    assert mock_get.call_count == 1


@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_empty_global_quote_raises(mock_get):
    mock_get.return_value = _resp({"Global Quote": {}})
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="No price returned"):
        provider.get_quotes(["UNKNOWN"], currency_hints={"UNKNOWN": "USD"})


@patch("app.market_data.alpha_vantage_provider.time.sleep")
@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_http_error_retries_then_raises(mock_get, mock_sleep):
    mock_get.side_effect = httpx.HTTPError("timeout")
    provider = AlphaVantageProvider("key")
    with pytest.raises(MarketDataError, match="3 attempts"):
        provider.get_quotes(["AAPL"], currency_hints={"AAPL": "USD"})
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


@patch("app.market_data.alpha_vantage_provider.time.sleep")
@patch("app.market_data.alpha_vantage_provider.httpx.get")
def test_http_status_error_does_not_leak_api_key(mock_get, mock_sleep):
    provider = AlphaVantageProvider(api_key="SECRET_KEY_123")
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized for url 'https://www.alphavantage.co/query?apikey=SECRET_KEY_123'",
        request=MagicMock(),
        response=mock_response,
    )
    mock_get.return_value = mock_response
    with pytest.raises(MarketDataError) as exc_info:
        provider.get_quotes(["AAPL"], currency_hints={"AAPL": "USD"})
    msg = str(exc_info.value)
    assert "SECRET_KEY_123" not in msg
    assert "apikey" not in msg
    assert "HTTP 401" in msg


def test_currency_metadata_is_required_before_network_call():
    provider = AlphaVantageProvider("key")

    with pytest.raises(MarketDataError, match="IBM"):
        provider.get_quotes(["IBM"])
