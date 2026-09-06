"""Unit tests for YahooTickerSearchProvider (httpx-based)."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import MarketDataError
from app.market_data.yahoo_search_provider import YahooTickerSearchProvider


def _resp(quotes: list) -> MagicMock:
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {"quotes": quotes}
    return m


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_normalizes_output_fields(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NMS",
         "exchDisp": "NASDAQ", "quoteType": "EQUITY", "currency": "USD"},
    ])
    provider = YahooTickerSearchProvider()
    results = provider.search("AAPL")
    assert results == [
        {"symbol": "AAPL", "name": "YF · Apple Inc.", "exchange": "NASDAQ", "type": "EQUITY", "provider": "yahoo", "currency": "USD"},
    ]


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_exchange_prefers_display_name(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "VWCE.DE", "shortname": "Vanguard FTSE All-World", "exchange": "GER",
         "exchDisp": "XETRA", "quoteType": "ETF"},
    ])
    provider = YahooTickerSearchProvider()
    assert provider.search("VWCE")[0]["exchange"] == "XETRA"


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_exchange_falls_back_to_code_without_display_name(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NMS", "quoteType": "EQUITY"},
    ])
    provider = YahooTickerSearchProvider()
    assert provider.search("AAPL")[0]["exchange"] == "NMS"


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_uses_longname_when_shortname_absent(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "VWCE.DE", "longname": "Vanguard FTSE All-World UCITS ETF", "exchange": "GER", "quoteType": "ETF"},
    ])
    provider = YahooTickerSearchProvider()
    results = provider.search("VWCE")
    assert results[0]["name"] == "YF · Vanguard FTSE All-World UCITS ETF"


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_filters_out_disallowed_types(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "AAPL", "shortname": "Apple", "exchange": "NMS", "quoteType": "EQUITY"},
        {"symbol": "AAPL221216C00150000", "shortname": "Option", "exchange": "OPR", "quoteType": "OPTION"},
        {"symbol": "^GSPC", "shortname": "S&P 500", "exchange": "SNP", "quoteType": "INDEX"},
    ])
    provider = YahooTickerSearchProvider()
    results = provider.search("AAPL")
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL"


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_missing_quotes_key_raises(mock_get):
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {}
    mock_get.return_value = m
    provider = YahooTickerSearchProvider()
    with pytest.raises(MarketDataError):
        provider.search("XXXX")


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_http_error_propagates(mock_get):
    mock_get.side_effect = Exception("connection refused")
    provider = YahooTickerSearchProvider()
    with pytest.raises(Exception, match="connection refused"):
        provider.search("AAPL")


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_provider_field_is_yahoo(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "BTC-USD", "shortname": "Bitcoin USD", "exchange": "CCC", "quoteType": "CRYPTOCURRENCY"},
    ])
    provider = YahooTickerSearchProvider()
    results = provider.search("BTC")
    assert results[0]["provider"] == "yahoo"


@patch("app.market_data.yahoo_search_provider.httpx.get")
def test_name_prefix_is_yf_label(mock_get):
    mock_get.return_value = _resp([
        {"symbol": "SPY", "shortname": "SPDR S&P 500 ETF", "exchange": "PCX", "quoteType": "ETF"},
    ])
    provider = YahooTickerSearchProvider()
    results = provider.search("SPY")
    assert results[0]["name"].startswith("YF · ")
