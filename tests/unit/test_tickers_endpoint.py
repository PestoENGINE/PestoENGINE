# tests/unit/test_tickers_endpoint.py
"""Unit tests for GET /v1/tickers/search."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ticker_search_provider
from app.main import app
from app.market_data.base import AbstractTickerSearchProvider


@pytest.fixture
def mock_search_provider() -> MagicMock:
    return MagicMock(spec=AbstractTickerSearchProvider)


@pytest.fixture
def client(mock_search_provider: MagicMock) -> TestClient:
    app.dependency_overrides[get_ticker_search_provider] = lambda: mock_search_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _quote(symbol: str, shortname: str, exchange: str, quote_type: str) -> dict:
    return {
        "symbol": symbol,
        "shortname": shortname,
        "exchange": exchange,
        "quoteType": quote_type,
    }


def test_returns_matching_results(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        _quote("VWCE.DE", "Vanguard FTSE All-World", "XETRA", "ETF")
    ]
    resp = client.get("/v1/tickers/search?q=VWCE")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["ticker"] == "VWCE.DE"
    assert results[0]["name"] == "Vanguard FTSE All-World"
    assert results[0]["exchange"] == "XETRA"
    assert results[0]["type"] == "ETF"


def test_index_type_excluded(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        _quote("VWCE.DE", "Vanguard FTSE All-World", "XETRA", "ETF"),
        _quote("^GSPC", "S&P 500", "SNP", "INDEX"),
    ]
    resp = client.get("/v1/tickers/search?q=SP500")
    assert resp.status_code == 200
    tickers = [r["ticker"] for r in resp.json()["results"]]
    assert "^GSPC" not in tickers
    assert "VWCE.DE" in tickers


def test_future_type_excluded(client, mock_search_provider):
    mock_search_provider.search.return_value = [_quote("ES=F", "E-Mini S&P 500", "CME", "FUTURE")]
    resp = client.get("/v1/tickers/search?q=ES")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_option_type_excluded(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        _quote("AAPL240119C00150000", "AAPL Call", "OPR", "OPTION")
    ]
    resp = client.get("/v1/tickers/search?q=AAPL")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_crypto_included(client, mock_search_provider):
    mock_search_provider.search.return_value = [_quote("BTC-USD", "Bitcoin USD", "CCC", "CRYPTOCURRENCY")]
    resp = client.get("/v1/tickers/search?q=BTC")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["ticker"] == "BTC-USD"


def test_currency_included(client, mock_search_provider):
    mock_search_provider.search.return_value = [_quote("EURCHF=X", "EUR/CHF", "CCY", "CURRENCY")]
    resp = client.get("/v1/tickers/search?q=EURCHF")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["ticker"] == "EURCHF=X"


def test_empty_results(client, mock_search_provider):
    mock_search_provider.search.return_value = []
    resp = client.get("/v1/tickers/search?q=XXXX")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_shortname_fallback_to_longname(client, mock_search_provider):
    mock_search_provider.search.return_value = [{
        "symbol": "VAGF.DE",
        "longname": "Vanguard Global Aggregate Bond",
        "exchange": "XETRA",
        "quoteType": "ETF",
    }]
    resp = client.get("/v1/tickers/search?q=VAGF")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["name"] == "Vanguard Global Aggregate Bond"


def test_missing_q_returns_422(client):
    resp = client.get("/v1/tickers/search")
    assert resp.status_code == 422


def test_single_char_q_returns_422(client):
    resp = client.get("/v1/tickers/search?q=V")
    assert resp.status_code == 422


def test_search_exception_returns_503(client, mock_search_provider):
    mock_search_provider.search.side_effect = Exception("timeout")
    resp = client.get("/v1/tickers/search?q=VWCE")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Market data unavailable"


def test_equity_included(client, mock_search_provider):
    mock_search_provider.search.return_value = [_quote("AAPL", "Apple Inc.", "NMS", "EQUITY")]
    resp = client.get("/v1/tickers/search?q=AAPL")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["ticker"] == "AAPL"


def test_mutualfund_included(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        _quote("VFIAX", "Vanguard 500 Index Fund", "NAS", "MUTUALFUND")
    ]
    resp = client.get("/v1/tickers/search?q=VFIAX")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["ticker"] == "VFIAX"


def test_empty_name_when_both_names_absent(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        {"symbol": "XYZ", "exchange": "TSX", "quoteType": "EQUITY"}
    ]
    resp = client.get("/v1/tickers/search?q=XYZ")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["name"] == ""
