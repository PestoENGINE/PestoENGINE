"""Unit tests for AlphaVantageSearchProvider."""

from unittest.mock import MagicMock, patch

import pytest

from app.market_data.alpha_vantage_search_provider import AlphaVantageSearchProvider


def _resp(body: dict) -> MagicMock:
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = body
    return m


_SAMPLE_MATCHES = [
    {"1. symbol": "IBM", "2. name": "International Business Machines", "3. type": "Equity", "4. region": "United States"},
    {"1. symbol": "IVVB11.SAO", "2. name": "iShares Core S&P 500 ETF", "3. type": "ETF", "4. region": "Brazil/Sao Paolo"},
]


def test_raises_on_empty_api_key():
    with pytest.raises(ValueError, match="non-empty api_key"):
        AlphaVantageSearchProvider("")


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_normalizes_output_fields(mock_get):
    mock_get.return_value = _resp({"bestMatches": [_SAMPLE_MATCHES[0]]})
    provider = AlphaVantageSearchProvider("key")
    results = provider.search("IBM")
    assert results == [
        {"symbol": "IBM", "name": "AV · International Business Machines", "exchange": "United States", "type": "EQUITY", "provider": "alphavantage"},
    ]


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_maps_equity_type(mock_get):
    mock_get.return_value = _resp({"bestMatches": [_SAMPLE_MATCHES[0]]})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("IBM")[0]["type"] == "EQUITY"


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_maps_etf_type(mock_get):
    mock_get.return_value = _resp({"bestMatches": [_SAMPLE_MATCHES[1]]})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("IVV")[0]["type"] == "ETF"


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_filters_unknown_types(mock_get):
    mock_get.return_value = _resp({"bestMatches": [
        {"1. symbol": "FOO", "2. name": "Foo", "3. type": "Unknown", "4. region": "US"},
    ]})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("FOO") == []


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_name_prefix_is_av_label(mock_get):
    mock_get.return_value = _resp({"bestMatches": [_SAMPLE_MATCHES[0]]})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("IBM")[0]["name"].startswith("AV · ")


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_provider_field_is_alphavantage(mock_get):
    mock_get.return_value = _resp({"bestMatches": [_SAMPLE_MATCHES[0]]})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("IBM")[0]["provider"] == "alphavantage"


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_rate_limit_note_returns_empty(mock_get):
    mock_get.return_value = _resp({"Note": "Thank you for using Alpha Vantage..."})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("IBM") == []


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_missing_best_matches_returns_empty(mock_get):
    mock_get.return_value = _resp({})
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("XXXX") == []


@patch("app.market_data.alpha_vantage_search_provider.httpx.get")
def test_http_error_returns_empty(mock_get):
    mock_get.side_effect = Exception("connection refused")
    provider = AlphaVantageSearchProvider("key")
    assert provider.search("IBM") == []
