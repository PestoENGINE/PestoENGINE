"""Unit tests for Pydantic schema validation (AssetIn, RebalanceRequest)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.request import AssetIn, RebalanceRequest


def _asset(**kwargs) -> dict:
    return {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0, **kwargs}


def _request(**kwargs) -> dict:
    return {
        "only_buy": True,
        "increment": 100.0,
        "base_currency": "EUR",
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


def test_percentage_fee_cap_error_carries_stable_code():
    with pytest.raises(ValidationError) as exc_info:
        AssetIn(**_asset(fees=101.0, percentage_fee=True))
    err = exc_info.value.errors()[0]
    assert err["type"] == "percentage_fee_cap"
    assert err["ctx"]["fees"] == 101.0


def test_asset_percentage_fee_exactly_100_is_valid():
    a = AssetIn(**_asset(fees=100.0, percentage_fee=True))
    assert a.percentage_fee is True


def test_asset_default_percentage_fee_is_false():
    a = AssetIn(**_asset())
    assert a.percentage_fee is False


def test_asset_currency_is_normalized_and_invalid_code_is_rejected():
    assert AssetIn(**_asset(currency=" eur ")).currency == "EUR"
    with pytest.raises(ValidationError):
        AssetIn(**_asset(currency="EURO"))


# ---------------------------------------------------------------------------
# RebalanceRequest validation
# ---------------------------------------------------------------------------

def test_request_percentages_not_summing_to_100_raises():
    with pytest.raises(ValidationError):
        RebalanceRequest(
            only_buy=True,
            increment=100.0,
            base_currency="EUR",
            assets=[
                AssetIn(ticker="A", desired_percentage=60.0, shares=0, fees=0),
                AssetIn(ticker="B", desired_percentage=30.0, shares=0, fees=0),
            ],
        )


def test_percentage_sum_error_carries_stable_code_and_total():
    with pytest.raises(ValidationError) as exc_info:
        RebalanceRequest(
            only_buy=True,
            increment=100.0,
            base_currency="EUR",
            assets=[
                AssetIn(ticker="A", desired_percentage=60.0, shares=0, fees=0),
                AssetIn(ticker="B", desired_percentage=30.0, shares=0, fees=0),
            ],
        )
    err = exc_info.value.errors()[0]
    assert err["type"] == "percentage_sum"
    assert err["ctx"]["total"] == 90.0


def test_request_percentages_summing_to_100_is_valid():
    req = RebalanceRequest(
        only_buy=True,
        increment=100.0,
        base_currency="EUR",
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


def test_request_default_fractional_shares_is_false():
    req = RebalanceRequest(**_request())
    assert req.fractional_shares is False


def test_request_fractional_shares_accepts_true():
    req = RebalanceRequest(**_request(fractional_shares=True))
    assert req.fractional_shares is True


def test_request_uses_decimal_for_every_monetary_input():
    req = RebalanceRequest(**_request(increment=0.1))
    assert isinstance(req.increment, Decimal)
    assert isinstance(req.assets[0].shares, Decimal)
    assert isinstance(req.assets[0].fees, Decimal)
    assert isinstance(req.assets[0].desired_percentage, Decimal)
    assert req.increment == Decimal("0.1")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_request_rejects_non_finite_numbers(value):
    with pytest.raises(ValidationError):
        RebalanceRequest(**_request(increment=value))


def test_base_currency_is_normalized():
    req = RebalanceRequest(**_request(base_currency=" eur "))
    assert req.base_currency == "EUR"


def test_base_currency_policy_is_loaded_from_backend_environment(monkeypatch):
    monkeypatch.setenv("BASE_CURRENCY", '["CHF"]')
    get_settings.cache_clear()
    try:
        assert RebalanceRequest(**_request(base_currency="CHF")).base_currency == "CHF"
        with pytest.raises(ValidationError):
            RebalanceRequest(**_request(base_currency="EUR"))
    finally:
        get_settings.cache_clear()
