"""Financial invariants and an exhaustive oracle independent of the planner."""

import random
from decimal import Decimal, localcontext
from itertools import product
from types import SimpleNamespace

import pytest

from app.rebalance.rebalance import redistribute_change_optimal
from app.schemas.request import RebalanceRequest
from app.services.rebalance_service import run_rebalance
from tests.helpers import make_quote

D = Decimal


def calculate(
    prices,
    shares,
    weights,
    fees,
    percentage,
    *,
    cash=0,
    only_buy=False,
    fractional=False,
    optimal=False,
):
    request = RebalanceRequest(
        only_buy=only_buy,
        increment=cash,
        base_currency="EUR",
        fractional_shares=fractional,
        optimal_redistribute=optimal,
        assets=[
            dict(
                ticker=f"T{i}", shares=held, desired_percentage=weight, fees=fee, percentage_fee=pct
            )
            for i, (held, weight, fee, pct) in enumerate(zip(shares, weights, fees, percentage))
        ],
    )
    registry = SimpleNamespace(get_quotes_for_assets=lambda _: [make_quote(p) for p in prices])
    result = run_rebalance(request, registry)
    with localcontext() as context:
        context.prec = 128
        assert result.change >= 0
        for asset, order in zip(request.assets, result.results):
            assert asset.shares + order.buy >= 0
            if only_buy:
                assert order.buy >= 0
            expected_fee = (
                (abs(order.allocated) * asset.fees / 100 if asset.percentage_fee else asset.fees)
                if order.buy
                else D(0)
            )
            assert order.fees == expected_fee
        assert result.total_fees == sum(r.fees for r in result.results)
        reconstructed = result.change + sum(r.allocated + r.fees for r in result.results)
        assert abs(request.increment - reconstructed) < D("1e-20")
    return result


@pytest.mark.parametrize("fractional,optimal", list(product([False, True], repeat=2)))
@pytest.mark.parametrize(
    "prices,shares,weights,fees,percentage",
    [
        ([30, 1], [3, 0], [50, 50], [0, 0], [False, False]),
        ([10, 10], [10, 0], [50, 50], [1, 0], [False, False]),
        ([10, 10], [100, 0], [0, 100], [1, 0], [True, False]),
        ([10, 10], [100, 0], [0, 100], [100, 0], [True, False]),
        (["0.0049", 1], ["0.123456", 0], [0, 100], [0, 0], [False, False]),
    ],
)
def test_sales_fund_buys_without_overselling(
    prices, shares, weights, fees, percentage, fractional, optimal
):
    calculate(prices, shares, weights, fees, percentage, fractional=fractional, optimal=optimal)


def test_seeded_portfolios_obey_financial_invariants():
    rng = random.Random(905)
    for _ in range(200):
        weight = rng.choice([0, 25, 50, 75, 100])
        calculate(
            [D(rng.randint(1, 10000)) / 100 for _ in range(2)],
            [D(rng.randint(0, 1000)) / 100 for _ in range(2)],
            [weight, 100 - weight],
            [rng.choice([0, 1, 5, 100]) for _ in range(2)],
            [rng.choice([False, True]) for _ in range(2)],
            cash=rng.choice([0, 1, 20, 100]),
            only_buy=rng.choice([False, True]),
            fractional=rng.choice([False, True]),
            optimal=rng.choice([False, True]),
        )


@pytest.mark.parametrize("optimal", [False, True])
def test_zero_initial_orders_can_open_an_affordable_position_with_one_fee(optimal):
    result = calculate(
        [60, 60], [0, 0], [50, 50], [5, 5], [False, False], cash=100, only_buy=True, optimal=optimal
    )
    assert sum(r.buy for r in result.results) == 1
    assert result.total_fees == 5
    assert result.change == 35


def test_dp_and_greedy_share_positive_gap_eligibility():
    results = [
        calculate(
            [6, 6],
            [10, 10],
            [50, 50],
            [0, 0],
            [False, False],
            cash=20,
            only_buy=True,
            optimal=optimal,
        )
        for optimal in [False, True]
    ]
    assert results[0].change == results[1].change == 2


def test_dp_matches_exhaustive_affordable_spend_with_opening_fees():
    rng = random.Random(1229)
    for _ in range(60):
        prices = [D(rng.randint(1, 9)) for _ in range(2)]
        fees = [D(rng.randint(0, 5)) for _ in range(2)]
        initial = [rng.randint(0, 1) for _ in range(2)]
        cash = D(rng.randint(1, 30))

        def cost(extra):
            return sum(
                extra[i] * prices[i] + (fees[i] if extra[i] and not initial[i] else 0)
                for i in range(2)
            )

        oracle = max(
            cost(extra) for extra in product(range(int(cash) + 1), repeat=2) if cost(extra) <= cash
        )
        updated, remaining = redistribute_change_optimal(
            True,
            initial,
            prices,
            [0, 0],
            [50, 50],
            cash,
            eligible=[True, True],
            opening_fees=fees,
        )
        assert remaining == cash - oracle
        assert remaining == cash - cost([updated[i] - initial[i] for i in range(2)])


def test_dp_fallback_preserves_mask_and_opening_fees():
    updated, remaining = redistribute_change_optimal(
        True,
        [1, 0],
        [1, 9999],
        [60, 40],
        [50, 50],
        10001,
        eligible=[False, True],
        opening_fees=[D(0), D(2)],
    )
    assert updated == [1, 1]
    assert remaining == 0


@pytest.mark.parametrize("fractional", [False, True])
def test_large_valid_orders_serialize_without_decimal_overflow(fractional):
    result = calculate(
        ["1e-18"], [0], [100], [0], [False], cash="1e12", only_buy=True, fractional=fractional
    )
    assert result.model_dump(mode="json")["results"][0]["buy"] == 1e30


def test_shares_and_subcent_prices_survive_response_serialization():
    result = calculate(["0.0049"], ["0.123456"], [100], [0], [False], only_buy=True)
    row = result.model_dump(mode="json")["results"][0]
    assert row["shares"] == 0.123456
    assert row["ticker_price"] == 0.0049
