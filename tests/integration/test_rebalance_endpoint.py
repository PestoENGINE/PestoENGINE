"""Integration tests for POST /v1/rebalance via FastAPI TestClient."""

from decimal import Decimal

import pytest

from app.core.exceptions import MarketDataError
from tests.helpers import make_quote, make_quotes

_SINGLE_ASSET_PAYLOAD = {
    "only_buy": True,
    "increment": 500.0,
    "base_currency": "EUR",
    "assets": [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 10.0},
    ],
}

_TWO_ASSET_PAYLOAD = {
    "only_buy": True,
    "increment": 1000.0,
    "base_currency": "EUR",
    "assets": [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 3.0},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0, "fees": 2.0},
    ],
}


def test_200_single_asset_fee(client, mock_registry):
    """POST /v1/rebalance returns 200 with correct buy and change.

    increment=500, price=100, fee=10
    net=490, buy=4, total_fees=10, change=90
    """
    mock_registry.get_quotes_for_assets.return_value = make_quotes({"A": 100.0})
    resp = client.post("/v1/rebalance", json=_SINGLE_ASSET_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["buy"] == 4
    assert body["results"][0]["ticker"] == "A"
    assert body["total_fees"] == 10.0
    assert body["change"] == 90.0


def test_200_two_assets(client, mock_registry):
    """POST /v1/rebalance returns correct totals for two assets with fees."""
    mock_registry.get_quotes_for_assets.return_value = make_quotes({"A": 50.0, "B": 100.0})
    resp = client.post("/v1/rebalance", json=_TWO_ASSET_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    by_ticker = {r["ticker"]: r for r in body["results"]}
    assert by_ticker["A"]["buy"] == 13
    assert by_ticker["B"]["buy"] == 3
    assert body["total_fees"] == 5.0
    assert body["change"] == 45.0


def test_422_percentages_do_not_sum_to_100(client):
    """Request with percentages summing to != 100 is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "base_currency": "EUR",
        "assets": [
            {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 0},
            {"ticker": "B", "desired_percentage": 30.0, "shares": 0, "fees": 0},
        ],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "percentage_sum"


def test_422_negative_increment(client):
    """Request with negative increment is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": -100.0,
        "base_currency": "EUR",
        "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422


def test_422_empty_assets(client):
    """Request with empty assets list is rejected with 422."""
    resp = client.post(
        "/v1/rebalance",
        json={
            "only_buy": True,
            "increment": 100.0,
            "base_currency": "EUR",
            "assets": [],
        },
    )
    assert resp.status_code == 422


def test_422_empty_ticker(client):
    """Request with empty ticker string is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "base_currency": "EUR",
        "assets": [{"ticker": "", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422


def test_422_percentage_fee_over_100(client):
    """Request with percentage_fee > 100 is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "base_currency": "EUR",
        "assets": [
            {"ticker": "A", "desired_percentage": 100.0, "shares": 0,
             "fees": 101.0, "percentage_fee": True},
        ],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "percentage_fee_cap"


def test_optimal_redistribute_flag_wired(client, mock_registry):
    """optimal_redistribute=True flag is passed through to the service."""
    mock_registry.get_quotes_for_assets.return_value = make_quotes({"A": 60.0, "B": 45.0})
    payload = {
        "only_buy": True,
        "increment": 200.0,
        "base_currency": "EUR",
        "optimal_redistribute": True,
        "assets": [
            {"ticker": "A", "desired_percentage": 50.0, "shares": 0, "fees": 0},
            {"ticker": "B", "desired_percentage": 50.0, "shares": 0, "fees": 0},
        ],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 200
    assert resp.json()["change"] >= 0.0


def test_fractional_shares_flag_wired(client, mock_registry):
    """fractional_shares=True yields a genuinely fractional buy and ~0 change.

    increment=1000, price=300, 100 % target
        buy = 1000/300 = 3.333333 (not a whole number), change = 0
    """
    mock_registry.get_quotes_for_assets.return_value = make_quotes({"A": 300.0})
    payload = {
        "only_buy": True,
        "increment": 1000.0,
        "base_currency": "EUR",
        "fractional_shares": True,
        "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    buy = body["results"][0]["buy"]
    assert buy == pytest.approx(3.333333, abs=1e-6)
    assert buy % 1 != 0  # fractional, not floored to a whole share
    assert 0 <= body["change"] < 0.01


def test_502_on_market_data_error(client, mock_registry):
    """MarketDataError from the registry is caught and returns HTTP 502."""
    mock_registry.get_quotes_for_assets.side_effect = MarketDataError("feed unavailable")
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "base_currency": "EUR",
        "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 502
    assert "feed unavailable" in resp.json()["detail"]


def test_legacy_payload_without_provider_field_succeeds(client, mock_registry):
    """Payload without 'provider' field (legacy localStorage) succeeds via fallback chain."""
    mock_registry.get_quotes_for_assets.return_value = make_quotes({"A": 100.0})
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "base_currency": "EUR",
        "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 200


def test_explicit_base_currency_converts_incompatible_live_quote(
    client,
    mock_registry,
    mock_fx_provider,
):
    mock_registry.get_quotes_for_assets.return_value = {
        "A": make_quote(100, currency="USD"),
    }
    mock_fx_provider.get_rates.return_value = {
        "USD": Decimal("0.8"),
    }
    payload = {
        **_SINGLE_ASSET_PAYLOAD,
        "base_currency": "EUR",
    }

    resp = client.post("/v1/rebalance", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    result = body["results"][0]
    assert result["ticker_price"] == 80.0
    assert result["buy"] == 6.0
    assert body["change"] == 10.0
    mock_fx_provider.get_rates.assert_called_once_with({"USD"}, "EUR")


def test_missing_base_currency_is_rejected_before_market_data(client, mock_registry):
    payload = dict(_TWO_ASSET_PAYLOAD)
    del payload["base_currency"]

    resp = client.post("/v1/rebalance", json=payload)

    assert resp.status_code == 422
    detail = resp.json()["detail"][0]
    assert detail["type"] == "missing"
    assert detail["loc"] == ["body", "base_currency"]
    mock_registry.get_quotes_for_assets.assert_not_called()


def test_unsupported_base_currency_is_rejected(client, mock_registry):
    payload = {
        **_SINGLE_ASSET_PAYLOAD,
        "base_currency": "SEK",
    }

    resp = client.post("/v1/rebalance", json=payload)

    assert resp.status_code == 422
    mock_registry.get_quotes_for_assets.assert_not_called()


def test_response_limits_ticker_price_to_two_decimals(client, mock_registry):
    mock_registry.get_quotes_for_assets.return_value = {
        "A": make_quote("1.239", currency="EUR"),
    }
    payload = {
        "only_buy": True,
        "increment": 1,
        "base_currency": "EUR",
        "fractional_shares": True,
        "assets": [
            {
                "ticker": "A",
                "desired_percentage": 100,
                "shares": 0,
                "fees": 0,
            },
        ],
    }

    resp = client.post("/v1/rebalance", json=payload)

    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["ticker_price"] == 1.23
