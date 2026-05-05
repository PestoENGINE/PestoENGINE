"""Unit tests for YahooTickerSearchProvider (httpx-based)."""

from unittest.mock import MagicMock, patch

import pytest

from app.market_data.yahoo_search_provider import YahooTickerSearchProvider


def _resp(quotes: list) -> MagicMock:
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {"quotes": quotes}
    return m


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_returns_quotes_list(mock_get):
    quotes = [{"symbol": "AAPL", "quoteType": "EQUITY"}]
    mock_get.return_value = _resp(quotes)
    provider = YahooTickerSearchProvider()
    assert provider.search("AAPL") == quotes


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_missing_quotes_key_returns_empty_list(mock_get):
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {}
    mock_get.return_value = m
    provider = YahooTickerSearchProvider()
    assert provider.search("XXXX") == []


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_http_error_propagates(mock_get):
    mock_get.side_effect = Exception("connection refused")
    provider = YahooTickerSearchProvider()
    with pytest.raises(Exception, match="connection refused"):
        provider.search("AAPL")
