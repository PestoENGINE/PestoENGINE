"""Orchestration of the DCA rebalancing flow."""

from app import rebalance
from app.core.exceptions import MarketDataError
from app.core.formatting import truncate2
from app.market_data.base import AbstractMarketDataProvider
from app.schemas.request import RebalanceRequest
from app.schemas.result import RebalanceResponse


def _effective_fee(fee: float, percentage_fee: bool, rebalance_amount: float) -> float:
    """Return the absolute fee for a single transaction."""
    if percentage_fee:
        return rebalance_amount * fee / 100.0
    return fee


def run_rebalance(
    request: RebalanceRequest,
    market_provider: AbstractMarketDataProvider,
) -> RebalanceResponse:
    """Compute optimal buy quantities for each asset in a portfolio.

    Args:
        request: A fully validated RebalanceRequest instance.
        market_provider: Provider used to fetch current market prices.

    Returns:
        A RebalanceResponse with per-asset results, total fees, and leftover change.
    """
    tickers = [a.ticker for a in request.assets]
    desired_pcts = [a.desired_percentage for a in request.assets]
    shares = [a.shares for a in request.assets]

    prices = market_provider.get_prices(tickers)
    try:
        ticker_prices = [round(prices[t], 2) for t in tickers]
    except KeyError as exc:
        raise MarketDataError(f"Price missing for ticker {exc}.") from exc

    for ticker, price in zip(tickers, ticker_prices):
        if price <= 0:
            raise MarketDataError(
                f"Invalid price for '{ticker}': {price}. Prices must be positive."
            )

    values = [s * p for s, p in zip(shares, ticker_prices)]
    total_value = sum(values)
    current_pcts = [v * 100.0 / total_value if total_value else 0.0 for v in values]

    rebalance_amounts = rebalance.calculate_rebalance(
        request.only_buy, request.increment, values, desired_pcts
    )

    effective_fees = [
        _effective_fee(a.fees, a.percentage_fee, r) if r > 0 else 0.0
        for a, r in zip(request.assets, rebalance_amounts)
    ]
    net_amounts = [
        max(0.0, r - ef) if r > 0 else r
        for r, ef in zip(rebalance_amounts, effective_fees)
    ]

    buy_quantities: list[int] = [int(r // p) for r, p in zip(net_amounts, ticker_prices)]

    spent = sum(b * p for b, p in zip(buy_quantities, ticker_prices))
    total_fees = sum(ef for ef, b in zip(effective_fees, buy_quantities) if b > 0)
    change = truncate2(request.increment - spent - total_fees)

    if request.optimal_redistribute:
        buy_quantities, change = rebalance.redistribute_change_optimal(
            request.only_buy,
            buy_quantities, ticker_prices,
            current_pcts, desired_pcts, change,
        )
    else:
        buy_quantities, change = rebalance.redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, change
        )

    results = [
        {
            "id": i,
            "ticker": ticker,
            "current_percentage": cur_pct,
            "desired_percentage": des_pct,
            "shares": share,
            "allocated": alloc,
            "ticker_price": price,
            "fees": ef if qty > 0 else 0.0,
            "buy": qty,
        }
        for i, (ticker, cur_pct, des_pct, share, alloc, price, ef, qty) in enumerate(
            zip(tickers, current_pcts, desired_pcts, shares,
                net_amounts, ticker_prices, effective_fees, buy_quantities)
        )
    ]

    return RebalanceResponse(results=results, total_fees=total_fees, change=change)
