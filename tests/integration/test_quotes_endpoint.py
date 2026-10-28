"""Integration tests for POST /v1/quotes (prices for REBALANCE_ENGINE=frontend)."""

from datetime import date
from decimal import Decimal

from app.core.exceptions import MarketDataError
from app.fx.ecb_provider import FxRates
from tests.helpers import make_quote

_PAYLOAD = {
    "base_currency": "EUR",
    "assets": [
        {"ticker": "vwce.de", "provider": "yahoo", "currency": "EUR"},
        {"ticker": "CSPX.L"},
    ],
}


def test_200_returns_base_currency_prices_in_request_order(client, mock_registry, mock_fx_provider):
    mock_registry.get_quotes_for_assets.return_value = [
        make_quote("132.4"),
        make_quote("600.5", currency="USD"),
    ]
    rates = FxRates(as_of=date(2026, 10, 27))
    rates["USD"] = Decimal("0.9")
    mock_fx_provider.get_rates.return_value = rates

    resp = client.post("/v1/quotes", json=_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert [q["ticker"] for q in body["quotes"]] == ["VWCE.DE", "CSPX.L"]
    assert [q["price"] for q in body["quotes"]] == [132.4, 540.45]
    assert body["base_currency"] == "EUR"
    assert body["fx_as_of"] == "2026-10-27"
    mock_fx_provider.get_rates.assert_called_once_with({"USD"}, "EUR")


def test_request_carries_no_holdings(client, mock_registry):
    """Only asset identity reaches the server; quantities and amounts stay in the browser."""
    mock_registry.get_quotes_for_assets.return_value = [make_quote(10)]
    payload = {"base_currency": "EUR", "assets": [{"ticker": "A", "shares": 12, "fees": 3}]}

    assert client.post("/v1/quotes", json=payload).status_code == 200
    (assets,) = mock_registry.get_quotes_for_assets.call_args.args
    assert not hasattr(assets[0], "shares")


def test_422_unsupported_base_currency(client):
    payload = {"base_currency": "XXX", "assets": [{"ticker": "A"}]}
    assert client.post("/v1/quotes", json=payload).status_code == 422


def test_422_too_many_assets(client):
    payload = {"base_currency": "EUR", "assets": [{"ticker": f"T{i}"} for i in range(101)]}
    resp = client.post("/v1/quotes", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "too_long"


def test_502_when_market_data_is_unavailable(client, mock_registry):
    mock_registry.get_quotes_for_assets.side_effect = MarketDataError("Yahoo down")
    assert client.post("/v1/quotes", json=_PAYLOAD).status_code == 502
