# tests/unit/test_tickers_endpoint.py
"""Unit tests for GET /v1/tickers/search."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_search_providers
from app.main import app
from app.market_data.base import AbstractTickerSearchProvider


@pytest.fixture
def mock_search_provider() -> MagicMock:
    return MagicMock(spec=AbstractTickerSearchProvider)


@pytest.fixture
def client(mock_search_provider: MagicMock) -> TestClient:
    app.dependency_overrides[get_search_providers] = lambda: [mock_search_provider]
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _result(symbol: str, name: str, exchange: str, type_: str, provider: str = "yahoo") -> dict:
    return {"symbol": symbol, "name": name, "exchange": exchange, "type": type_, "provider": provider}


def test_returns_matching_results(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        _result("VWCE.DE", "YF · Vanguard FTSE All-World", "XETRA", "ETF")
    ]
    resp = client.get("/v1/tickers/search?q=VWCE")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["ticker"] == "VWCE.DE"
    assert results[0]["name"] == "YF · Vanguard FTSE All-World"
    assert results[0]["exchange"] == "XETRA"
    assert results[0]["type"] == "ETF"
    assert results[0]["provider"] == "yahoo"


def test_provider_field_passed_through(client, mock_search_provider):
    mock_search_provider.search.return_value = [
        _result("IBM", "AV · IBM", "United States", "EQUITY", provider="alphavantage")
    ]
    resp = client.get("/v1/tickers/search?q=IBM")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["provider"] == "alphavantage"


def test_empty_results(client, mock_search_provider):
    mock_search_provider.search.return_value = []
    resp = client.get("/v1/tickers/search?q=XXXX")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


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


def test_multiple_providers_results_merged(mock_search_provider):
    """Results from two providers are merged into a single list."""
    provider_a = MagicMock(spec=AbstractTickerSearchProvider)
    provider_a.search.return_value = [_result("AAPL", "YF · Apple", "NMS", "EQUITY", "yahoo")]
    provider_b = MagicMock(spec=AbstractTickerSearchProvider)
    provider_b.search.return_value = [_result("AAPL", "AV · Apple Inc", "United States", "EQUITY", "alphavantage")]
    app.dependency_overrides[get_search_providers] = lambda: [provider_a, provider_b]
    try:
        with TestClient(app) as c:
            resp = c.get("/v1/tickers/search?q=AAPL")
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_one_provider_fails_other_succeeds(mock_search_provider):
    """If one provider raises, the other's results are still returned."""
    good = MagicMock(spec=AbstractTickerSearchProvider)
    good.search.return_value = [_result("AAPL", "YF · Apple", "NMS", "EQUITY", "yahoo")]
    bad = MagicMock(spec=AbstractTickerSearchProvider)
    bad.search.side_effect = Exception("AV down")
    app.dependency_overrides[get_search_providers] = lambda: [good, bad]
    try:
        with TestClient(app) as c:
            resp = c.get("/v1/tickers/search?q=AAPL")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["ticker"] == "AAPL"
    finally:
        app.dependency_overrides.clear()
