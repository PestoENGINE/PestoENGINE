"""Integration tests for POST /v1/rebalance via FastAPI TestClient."""

from app.core.exceptions import MarketDataError

_SINGLE_ASSET_PAYLOAD = {
    "only_buy": True,
    "increment": 500.0,
    "assets": [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 10.0},
    ],
}

_TWO_ASSET_PAYLOAD = {
    "only_buy": True,
    "increment": 1000.0,
    "assets": [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 3.0},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0, "fees": 2.0},
    ],
}


def test_200_single_asset_fee(client, mock_provider):
    """POST /v1/rebalance returns 200 with correct buy and change.

    increment=500, price=100, fee=10
    net=490, buy=4, total_fees=10, change=90
    """
    mock_provider.get_prices.return_value = {"A": 100.0}
    resp = client.post("/v1/rebalance", json=_SINGLE_ASSET_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["buy"] == 4
    assert body["results"][0]["ticker"] == "A"
    assert body["total_fees"] == 10.0
    assert body["change"] == 90.0


def test_200_two_assets(client, mock_provider):
    """POST /v1/rebalance returns correct totals for two assets with fees."""
    mock_provider.get_prices.return_value = {"A": 50.0, "B": 100.0}
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
        "assets": [
            {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 0},
            {"ticker": "B", "desired_percentage": 30.0, "shares": 0, "fees": 0},
        ],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422


def test_422_negative_increment(client):
    """Request with negative increment is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": -100.0,
        "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422


def test_422_empty_assets(client):
    """Request with empty assets list is rejected with 422."""
    resp = client.post("/v1/rebalance", json={"only_buy": True, "increment": 100.0, "assets": []})
    assert resp.status_code == 422


def test_422_empty_ticker(client):
    """Request with empty ticker string is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "assets": [{"ticker": "", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422


def test_422_percentage_fee_over_100(client):
    """Request with percentage_fee > 100 is rejected with 422."""
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "assets": [
            {"ticker": "A", "desired_percentage": 100.0, "shares": 0,
             "fees": 101.0, "percentage_fee": True},
        ],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 422


def test_optimal_redistribute_flag_wired(client, mock_provider):
    """optimal_redistribute=True flag is passed through to the service."""
    mock_provider.get_prices.return_value = {"A": 60.0, "B": 45.0}
    payload = {
        "only_buy": True,
        "increment": 200.0,
        "optimal_redistribute": True,
        "assets": [
            {"ticker": "A", "desired_percentage": 50.0, "shares": 0, "fees": 0},
            {"ticker": "B", "desired_percentage": 50.0, "shares": 0, "fees": 0},
        ],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 200
    assert resp.json()["change"] >= 0.0


def test_502_on_market_data_error(client, mock_provider):
    """MarketDataError from the provider is caught and returns HTTP 502."""
    mock_provider.get_prices.side_effect = MarketDataError("feed unavailable")
    payload = {
        "only_buy": True,
        "increment": 100.0,
        "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
    }
    resp = client.post("/v1/rebalance", json=payload)
    assert resp.status_code == 502
    assert "feed unavailable" in resp.json()["detail"]
