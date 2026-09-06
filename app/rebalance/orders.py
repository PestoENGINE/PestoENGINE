"""Turn target gaps into executable, cash-funded orders (no I/O)."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.core.formatting import truncate
from app.rebalance.rebalance import redistribute_change, redistribute_change_optimal

ZERO = Decimal(0)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class OrderPlan:
    quantities: list[Decimal]
    fees: list[Decimal]
    change: Decimal


def plan_orders(
    *,
    gaps: list[Decimal],
    prices: list[Decimal],
    shares: list[Decimal],
    fees: list[Decimal],
    percentage_fees: list[bool],
    increment: Decimal,
    current_percentages: list[Decimal],
    desired_percentages: list[Decimal],
    only_buy: bool,
    fractional: bool,
    optimal: bool,
) -> OrderPlan:
    """Sell at most owned shares, then fund buys from actual net proceeds.

    Flat fees apply once per nonzero order. Percentage fees apply to its actual
    notional. Quantities round toward zero, to whole shares or six decimals.
    Target gaps guide purchases; fees and rounding can prevent exact targets.
    """
    with localcontext() as context:
        context.prec = 128
        places = 6 if fractional else 0
        quantities = [ZERO] * len(prices)

        def order_fee(i: int, quantity: Decimal) -> Decimal:
            if not quantity:
                return ZERO
            return abs(quantity * prices[i]) * fees[i] / HUNDRED if percentage_fees[i] else fees[i]

        cash = increment
        if not only_buy:
            for i, gap in enumerate(gaps):
                if gap >= 0:
                    continue
                sold = truncate(min(-gap / prices[i], shares[i]), places)
                proceeds = sold * prices[i] - order_fee(i, sold)
                if sold and proceeds > 0:
                    quantities[i] = -sold
                    cash += proceeds

        positive = sum((max(gap, ZERO) for gap in gaps), ZERO)
        budget = min(cash, positive)
        for i, gap in enumerate(gaps):
            if gap <= 0 or not positive:
                continue
            allowance = min(cash, budget * gap / positive)
            marginal = prices[i] * (1 + fees[i] / HUNDRED) if percentage_fees[i] else prices[i]
            opening = ZERO if percentage_fees[i] else fees[i]
            quantity = truncate(max(ZERO, allowance - opening) / marginal, places)
            cost = quantity * prices[i] + order_fee(i, quantity)
            # Division may round up at the last context digit. Never spend it.
            if quantity and cost > cash:
                quantity -= Decimal(1).scaleb(-places)
                cost = quantity * prices[i] + order_fee(i, quantity)
            quantities[i] = quantity
            cash -= cost

        if not fractional:
            marginal_prices = [
                price * (1 + fee / HUNDRED) if pct else price
                for price, fee, pct in zip(prices, fees, percentage_fees)
            ]
            options = {
                "eligible": [gap > 0 for gap in gaps],
                "opening_fees": [ZERO if pct else fee for fee, pct in zip(fees, percentage_fees)],
            }
            args = (
                [int(q) for q in quantities],
                marginal_prices,
                current_percentages,
                desired_percentages,
                cash,
            )
            updated, cash = (
                redistribute_change_optimal(only_buy, *args, **options)
                if optimal
                else redistribute_change(*args, **options)
            )
            quantities = [Decimal(q) for q in updated]

        actual_fees = [order_fee(i, quantity) for i, quantity in enumerate(quantities)]
        return OrderPlan(quantities, actual_fees, cash)
