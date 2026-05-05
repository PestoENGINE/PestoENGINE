"""Unit tests for run_rebalance() - market provider mocked out."""

import pytest
from unittest.mock import MagicMock

from app.market_data.base import AbstractMarketDataProvider
from app.schemas.request import AssetIn, RebalanceRequest
from app.schemas.result import RebalanceResponse
from app.services.rebalance_service import run_rebalance


def _request(
    only_buy: bool,
    increment: float,
    asset_defs: list[dict],
    optimal_redistribute: bool = False,
) -> RebalanceRequest:
    return RebalanceRequest(
        only_buy=only_buy,
        increment=increment,
        optimal_redistribute=optimal_redistribute,
        assets=[
            AssetIn(
                ticker=d["ticker"],
                desired_percentage=d["desired_percentage"],
                shares=d.get("shares", 0.0),
                fees=d.get("fees", 0.0),
                percentage_fee=d.get("percentage_fee", False),
            )
            for d in asset_defs
        ],
    )


def _run(request: RebalanceRequest, prices: dict[str, float]) -> RebalanceResponse:
    provider = MagicMock(spec=AbstractMarketDataProvider)
    provider.get_prices.return_value = prices
    return run_rebalance(request, provider)


# ---------------------------------------------------------------------------
# Fee tests
# ---------------------------------------------------------------------------

def test_fee_deducted_from_allocated_and_change():
    """Fee reduces allocated amount; change = increment - spent - fee.

    increment=500, price=100, fee=10, desired=100 %
        gross alloc = 500, net = 490
        buy = floor(490/100) = 4, spent = 400
        total_fees = 10, change = 500 - 400 - 10 = 90
    """
    req = _request(True, 500.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 10.0},
    ])
    out = _run(req, {"A": 100.0})
    r = out.results[0]
    assert r.buy == 4
    assert r.allocated == pytest.approx(490.0, abs=0.01)
    assert out.total_fees == 10.0
    assert out.change == 90.0


def test_fee_larger_than_allocation_buy_zero_fee_excluded():
    """Asset whose fee exceeds gross allocation is clamped to 0.

    A gross alloc = 10 → net = max(0, 10-50) = 0 → buy_A = 0, fee_A excluded
    B gross alloc = 90 → buy_B = 4, redistribute → buy_B = 5, change = 0
    """
    req = _request(True, 100.0, [
        {"ticker": "A", "desired_percentage": 10.0, "shares": 0, "fees": 50.0},
        {"ticker": "B", "desired_percentage": 90.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 5.0, "B": 20.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy == 0
    assert by_ticker["B"].buy == 5
    assert out.total_fees == 0.0
    assert out.change == 0.0


def test_fees_both_assets_summed_in_total_fees():
    """total_fees = sum of fees for all assets whose buy quantity > 0."""
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 3.0},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0, "fees": 2.0},
    ])
    out = _run(req, {"A": 50.0, "B": 100.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy > 0
    assert by_ticker["B"].buy > 0
    assert out.total_fees == 5.0


def test_only_buy_false_fee_deducted_from_change():
    """In allow-sell mode, fee is still deducted from change.

    only_buy=False, increment=100, A: 100 %, shares=5 @ 20, fee=5
        gross rebalance = 100, net = 95
        buy = floor(95/20) = 4, spent = 80, total_fees = 5, change = 15
    """
    req = _request(False, 100.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 5.0, "fees": 5.0},
    ])
    out = _run(req, {"A": 20.0})
    assert out.results[0].buy == 4
    assert out.total_fees == 5.0
    assert out.change == 15.0


# ---------------------------------------------------------------------------
# Change (remainder) tests
# ---------------------------------------------------------------------------

def test_no_fees_change_equals_rounding_leftover():
    """Without fees, change = increment - spent (pure rounding leftover).

    increment=1000, price=300 → buy=3, spent=900, change=100
    """
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 300.0})
    assert out.results[0].buy == 3
    assert out.total_fees == 0.0
    assert out.change == 100.0


def test_fee_reserved_cash_not_spent_in_redistribution():
    """Redistribution must NOT consume fee-reserved cash.

    increment=1000, price=200, fee=50
        net = 950, buy = 4, spent = 800
        total_fees = 50, change = 1000 - 800 - 50 = 150
        redistribute: floor(150/200) = 0 extra
    """
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 50.0},
    ])
    out = _run(req, {"A": 200.0})
    assert out.results[0].buy == 4
    assert out.total_fees == 50.0
    assert out.change == 150.0


def test_change_zero_when_increment_perfectly_divisible():
    """change = 0 when increment is exactly divisible into shares."""
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 100.0})
    assert out.results[0].buy == 10
    assert out.total_fees == 0.0
    assert out.change == 0.0


def test_redistribution_buys_extra_share_when_change_covers_price():
    """When change >= price of eligible asset, extra share is bought."""
    req = _request(True, 1050.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 50.0})
    assert out.results[0].buy == 21
    assert out.change == 0.0


def test_change_two_assets_with_fees():
    """End-to-end change with two assets both paying fees.

    increment=1000, A: 60 %, price=50, fee=3; B: 40 %, price=100, fee=2
        A net=597 → buy=11; B net=398 → buy=3; spent=850, total_fees=5, change=145
        Redistribute: A gets 2 extra → buy_A=13, change=45
    """
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 3.0},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0, "fees": 2.0},
    ])
    out = _run(req, {"A": 50.0, "B": 100.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy == 13
    assert by_ticker["B"].buy == 3
    assert out.total_fees == 5.0
    assert out.change == 45.0


def test_only_buy_false_change_when_price_exceeds_leftover():
    """In allow-sell mode, change stays when no eligible share fits."""
    req = _request(False, 200.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 150.0})
    assert out.results[0].buy == 1
    assert out.change == 50.0


def test_only_buy_false_greedy_redistributes_change():
    """In allow-sell mode, greedy redistribution runs when change covers a price.

    A: buy=4 (spent=52), B: buy=2 (spent=34), change=14
    Greedy: A gets 1 extra → buy_A=5, change=1
    """
    req = _request(False, 100.0, [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 0.0},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 13.0, "B": 17.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy == 5
    assert by_ticker["B"].buy == 2
    assert out.change == 1.0


# ---------------------------------------------------------------------------
# optimal_redistribute flag
# ---------------------------------------------------------------------------

def test_flag_off_keeps_greedy_behaviour():
    """Default optimal_redistribute=False uses greedy redistribution.

    increment=100, A: price=60, B: price=45
        buy_A=0, buy_B=1, change=55
        Greedy: B gets 1 extra → buy_B=2, change=10
    """
    req = _request(True, 100.0, [
        {"ticker": "A", "desired_percentage": 50.0, "shares": 0, "fees": 0.0},
        {"ticker": "B", "desired_percentage": 50.0, "shares": 0, "fees": 0.0},
    ], optimal_redistribute=False)
    out = _run(req, {"A": 60.0, "B": 45.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy == 0
    assert by_ticker["B"].buy == 2
    assert out.change == 10.0


def test_flag_on_never_worse_than_greedy_in_buy_only():
    """optimal_redistribute=True leaves <= cash on the table than greedy."""
    assets_def = [
        {"ticker": "A", "desired_percentage": 50.0, "shares": 0, "fees": 0.0},
        {"ticker": "B", "desired_percentage": 50.0, "shares": 0, "fees": 0.0},
    ]
    prices = {"A": 60.0, "B": 45.0}
    out_greedy = _run(_request(True, 200.0, assets_def, optimal_redistribute=False), prices)
    out_optimal = _run(_request(True, 200.0, assets_def, optimal_redistribute=True), prices)
    assert out_optimal.change <= out_greedy.change


def test_flag_on_applies_in_allow_sell_mode():
    """DP is called when only_buy=False and optimal_redistribute=True."""
    req = _request(False, 100.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0.0},
    ], optimal_redistribute=True)
    out = _run(req, {"A": 30.0})
    assert out.results[0].buy == 3
    assert out.change == 10.0


def test_flag_on_allow_sell_exact_fit():
    """DP with price dividing increment exactly → change=0."""
    req = _request(False, 150.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0.0},
    ], optimal_redistribute=True)
    out = _run(req, {"A": 50.0})
    assert out.results[0].buy == 3
    assert out.change == 0.0


# ---------------------------------------------------------------------------
# Percentage fee tests
# ---------------------------------------------------------------------------

def test_percentage_fee_deducted_correctly():
    """1 % fee on 1000 increment → effective fee = 10.

    net=990, buy=floor(990/100)=9, spent=900, total_fees=10, change=90
    """
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0,
         "fees": 1.0, "percentage_fee": True},
    ])
    out = _run(req, {"A": 100.0})
    r = out.results[0]
    assert r.buy == 9
    assert r.allocated == pytest.approx(990.0, abs=0.01)
    assert out.total_fees == pytest.approx(10.0, abs=0.01)
    assert out.change == pytest.approx(90.0, abs=0.01)


def test_percentage_fee_not_counted_when_buy_is_zero():
    """Percentage fee on a buy=0 asset must not appear in total_fees."""
    req = _request(True, 100.0, [
        {"ticker": "A", "desired_percentage": 10.0, "shares": 900,
         "fees": 5.0, "percentage_fee": True},
        {"ticker": "B", "desired_percentage": 90.0, "shares": 0, "fees": 0.0},
    ])
    out = _run(req, {"A": 5.0, "B": 20.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy == 0
    assert out.total_fees == pytest.approx(0.0, abs=0.01)


def test_mixed_fee_types():
    """One fixed-fee and one percentage-fee asset - correct totals.

    A: 60 %, price=50, fee=3 (fixed) → ef=3, net=597, buy=11
    B: 40 %, price=100, fee=1 % → ef=4, net=396, buy=3
    spent=850, total_fees=7, change=143
    Redistribute: A gets 2 extra → buy_A=13, change=43
    """
    req = _request(True, 1000.0, [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0,
         "fees": 3.0, "percentage_fee": False},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0,
         "fees": 1.0, "percentage_fee": True},
    ])
    out = _run(req, {"A": 50.0, "B": 100.0})
    by_ticker = {r.ticker: r for r in out.results}
    assert by_ticker["A"].buy == 13
    assert by_ticker["B"].buy == 3
    assert out.total_fees == pytest.approx(7.0, abs=0.01)
    assert out.change == pytest.approx(43.0, abs=0.01)


def test_percentage_fee_allow_sell():
    """Percentage fee works correctly in allow-sell mode.

    only_buy=False, increment=100, A: 100 %, shares=5, price=20, fee=2 %
        ef=2, net=98, buy=4, spent=80, total_fees=2, change=18
    """
    req = _request(False, 100.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 5.0,
         "fees": 2.0, "percentage_fee": True},
    ])
    out = _run(req, {"A": 20.0})
    assert out.results[0].buy == 4
    assert out.total_fees == pytest.approx(2.0, abs=0.01)
    assert out.change == pytest.approx(18.0, abs=0.01)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

def test_missing_ticker_in_prices_raises_market_data_error():
    """get_prices returning a partial dict raises MarketDataError."""
    from app.core.exceptions import MarketDataError
    req = _request(True, 100.0, [
        {"ticker": "A", "desired_percentage": 60.0, "shares": 0, "fees": 0},
        {"ticker": "B", "desired_percentage": 40.0, "shares": 0, "fees": 0},
    ])
    with pytest.raises(MarketDataError, match="Price missing for ticker"):
        _run(req, {"A": 50.0})


def test_zero_price_raises_market_data_error():
    """A zero price from the provider raises MarketDataError."""
    from app.core.exceptions import MarketDataError
    req = _request(True, 100.0, [
        {"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0},
    ])
    with pytest.raises(MarketDataError, match="Invalid price"):
        _run(req, {"A": 0.0})
