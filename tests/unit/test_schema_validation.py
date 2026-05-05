"""Unit tests for Pydantic schema validation (AssetIn, RebalanceRequest)."""

import pytest
from pydantic import ValidationError

from app.schemas.request import AssetIn, RebalanceRequest


def _asset(**kwargs) -> dict:
    return {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0, **kwargs}


def _request(**kwargs) -> dict:
    return {
        "only_buy": True,
        "increment": 100.0,
        "assets": [_asset()],
        **kwargs,
    }


# ---------------------------------------------------------------------------
# AssetIn validation
# ---------------------------------------------------------------------------

def test_asset_empty_ticker_raises():
    with pytest.raises(ValidationError):
        AssetIn(**_asset(ticker=""))


def test_asset_desired_percentage_zero_allowed():
    AssetIn(**_asset(desired_percentage=0.0, ticker="A"))


def test_asset_desired_percentage_over_100_raises():
    with pytest.raises(ValidationError):
        AssetIn(**_asset(desired_percentage=100.01))


def test_asset_negative_shares_raises():
    with pytest.raises(ValidationError):
        AssetIn(**_asset(shares=-1.0))


def test_asset_negative_fees_raises():
    with pytest.raises(ValidationError):
        AssetIn(**_asset(fees=-0.01))


def test_asset_percentage_fee_over_100_raises():
    with pytest.raises(ValidationError):
        AssetIn(**_asset(fees=101.0, percentage_fee=True))


def test_asset_percentage_fee_exactly_100_is_valid():
    a = AssetIn(**_asset(fees=100.0, percentage_fee=True))
    assert a.percentage_fee is True


def test_asset_default_percentage_fee_is_false():
    a = AssetIn(**_asset())
    assert a.percentage_fee is False


# ---------------------------------------------------------------------------
# RebalanceRequest validation
# ---------------------------------------------------------------------------

def test_request_percentages_not_summing_to_100_raises():
    with pytest.raises(ValidationError):
        RebalanceRequest(
            only_buy=True,
            increment=100.0,
            assets=[
                AssetIn(ticker="A", desired_percentage=60.0, shares=0, fees=0),
                AssetIn(ticker="B", desired_percentage=30.0, shares=0, fees=0),
            ],
        )


def test_request_percentages_summing_to_100_is_valid():
    req = RebalanceRequest(
        only_buy=True,
        increment=100.0,
        assets=[
            AssetIn(ticker="A", desired_percentage=60.0, shares=0, fees=0),
            AssetIn(ticker="B", desired_percentage=40.0, shares=0, fees=0),
        ],
    )
    assert len(req.assets) == 2


def test_request_negative_increment_raises():
    with pytest.raises(ValidationError):
        RebalanceRequest(**_request(increment=-1.0))


def test_request_empty_assets_raises():
    with pytest.raises(ValidationError):
        RebalanceRequest(**_request(assets=[]))


def test_request_default_optimal_redistribute_is_false():
    req = RebalanceRequest(**_request())
    assert req.optimal_redistribute is False
