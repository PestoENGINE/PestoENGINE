"""Orchestration of the DCA rebalancing flow."""

import time
from functools import lru_cache

from opentelemetry import metrics as _otel_metrics
from opentelemetry import trace as _otel_trace

from app import rebalance
from app.core.exceptions import MarketDataError
from app.core.formatting import truncate, truncate2

# Decimal places kept for a fractional share quantity. Finer than any broker;
# truncating down keeps the residual unspent cash below a cent.
_FRACTIONAL_PLACES = 6
from app.market_data.provider_registry import ProviderRegistry
from app.schemas.request import RebalanceRequest
from app.schemas.result import RebalanceResponse


def _apply_fee(
    rebalance_amount: float, fee: float, percentage_fee: bool
) -> tuple[float, float]:
    """Return (qty_target, effective_fee) for a single transaction.

    qty_target is divided by price (floor) to obtain the share count.
    effective_fee is 0 for percentage-fee transactions - it is recomputed after
    the share count is known, because the fee must apply to the actual transaction value.

    - buy  flat fee (r > 0):   qty_target = r - fee          (fee reduces budget; 0 if fee >= r)
    - buy  pct fee  (r > 0):   qty_target = r / (1 + fee%)   (deflated so that
                                qty * price * (1 + fee%) ≈ r, total spend ≈ target)
    - sell flat fee (r < 0):   qty_target = r + fee          (flat cost reduces net proceeds)
    - sell pct fee  (r < 0):   qty_target = r / (1 - fee%)   (inflated so that
                                qty * price * (1 - fee%) ≈ r, net proceeds ≈ target)
    """
    if rebalance_amount == 0:
        return 0.0, 0.0

    if rebalance_amount > 0:
        if not percentage_fee:
            net = rebalance_amount - fee
            return (0.0, 0.0) if net <= 0 else (net, fee)
        # pct buy: deflate target so qty * price * (1 + fee%) ≈ r
        return rebalance_amount / (1.0 + fee / 100.0), 0.0  # fee recomputed after qty

    # sell
    if percentage_fee:
        factor = 1.0 - fee / 100.0
        if factor <= 0:
            return 0.0, 0.0
        return rebalance_amount / factor, 0.0  # fee recomputed after qty
    else:
        net = rebalance_amount + fee
        return (0.0, 0.0) if net >= 0 else (net, fee)


@lru_cache(maxsize=1)
def _rebalance_instruments(
    meter_provider: _otel_metrics.MeterProvider | None = None,
) -> tuple:
    mp = meter_provider or _otel_metrics.get_meter_provider()
    meter = mp.get_meter("pestoengine.rebalance")
    return (
        meter.create_histogram(
            "pestoengine_rebalance_duration_seconds",
            description="End-to-end rebalance computation duration",
            unit="s",
        ),
        meter.create_histogram(
            "pestoengine_rebalance_tickers",
            description="Number of tickers in a rebalance request",
            unit="{ticker}",
        ),
    )


_tracer = _otel_trace.get_tracer("pestoengine.rebalance")


def run_rebalance(
    request: RebalanceRequest,
    registry: ProviderRegistry,
    *,
    meter_provider: _otel_metrics.MeterProvider | None = None,
    tracer_provider: _otel_trace.TracerProvider | None = None,
) -> RebalanceResponse:
    dur_hist, ticker_hist = _rebalance_instruments(meter_provider)
    algorithm = "dp" if request.optimal_redistribute else "greedy"
    _start = time.perf_counter()
    tracer = (
        tracer_provider.get_tracer("pestoengine.rebalance")
        if tracer_provider is not None
        else _tracer
    )
    with tracer.start_as_current_span(
        "rebalance_compute",
        attributes={
            "rebalance.algorithm": algorithm,
            "rebalance.tickers.count": len(request.assets),
            "rebalance.only_buy": request.only_buy,
            "rebalance.increment": request.increment,
        },
    ):
        try:
            tickers = [a.ticker for a in request.assets]
            desired_pcts = [a.desired_percentage for a in request.assets]
            shares = [a.shares for a in request.assets]

            prices = registry.get_prices_for_assets(request.assets)
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

            qty_targets, effective_fees_raw = zip(
                *[_apply_fee(r, a.fees, a.percentage_fee) for a, r in zip(request.assets, rebalance_amounts)]
            )

            # Fractional mode buys the exact quantity each budget affords, so every
            # asset lands on its target precisely. Whole-share mode floors to integer
            # share counts and relies on the redistribution step to place the leftover.
            buy_quantities: list[float]
            if request.fractional_shares:
                buy_quantities = [truncate(t / p, _FRACTIONAL_PLACES) for t, p in zip(qty_targets, ticker_prices)]
            else:
                buy_quantities = [int(t // p) for t, p in zip(qty_targets, ticker_prices)]

            # First pass: compute fees and change budget to feed into redistribution.
            effective_fees = [
                abs(b * p) * a.fees / 100.0 if (b != 0 and a.percentage_fee) else ef
                for ef, a, b, p in zip(effective_fees_raw, request.assets, buy_quantities, ticker_prices)
            ]

            buy_costs     = sum( b * p for b, p in zip(buy_quantities, ticker_prices) if b > 0)
            sell_proceeds = sum(-b * p for b, p in zip(buy_quantities, ticker_prices) if b < 0)
            buy_fees      = sum(ef for ef, b in zip(effective_fees, buy_quantities) if b > 0)
            sell_fees     = sum(ef for ef, b in zip(effective_fees, buy_quantities) if b < 0)
            change = truncate2((request.increment + sell_proceeds - sell_fees) - (buy_costs + buy_fees))

            # Pct-fee assets are repriced to include the per-share fee so that redistribute
            # sees the true cash cost of each extra share and does not overspend the budget.
            redistribute_prices = [
                p * (1.0 + a.fees / 100.0) if a.percentage_fee else p
                for p, a in zip(ticker_prices, request.assets)
            ]

            # Fractional mode already spent the budget exactly, so there is no
            # integer leftover to place: the redistribution step is skipped entirely
            # (and optimal_redistribute has no effect under fractional shares).
            if not request.fractional_shares:
                if request.optimal_redistribute:
                    buy_quantities, _ = rebalance.redistribute_change_optimal(
                        request.only_buy,
                        buy_quantities, redistribute_prices,
                        current_pcts, desired_pcts, change,
                    )
                else:
                    buy_quantities, _ = rebalance.redistribute_change(
                        buy_quantities, redistribute_prices,
                        current_pcts, desired_pcts, change
                    )

            # Second pass: recompute fees and change on final quantities.
            # Redistribution may have changed buy_quantities; percentage fees scale with actual shares.
            effective_fees = [
                abs(b * p) * a.fees / 100.0 if (b != 0 and a.percentage_fee) else ef
                for ef, a, b, p in zip(effective_fees_raw, request.assets, buy_quantities, ticker_prices)
            ]
            buy_costs  = sum( b * p for b, p in zip(buy_quantities, ticker_prices) if b > 0)
            buy_fees   = sum(ef     for ef, b in zip(effective_fees, buy_quantities) if b > 0)
            sell_fees  = sum(ef     for ef, b in zip(effective_fees, buy_quantities) if b < 0)
            total_fees = buy_fees + sell_fees
            change     = truncate2((request.increment + sell_proceeds - sell_fees) - (buy_costs + buy_fees))

            results = [
                {
                    "id": i,
                    "ticker": ticker,
                    "current_percentage": cur_pct,
                    "desired_percentage": des_pct,
                    "shares": share,
                    "allocated": qty * price,
                    "ticker_price": price,
                    "fees": ef if qty != 0 else 0.0,
                    "buy": qty,
                }
                for i, (ticker, cur_pct, des_pct, share, price, ef, qty) in enumerate(
                    zip(tickers, current_pcts, desired_pcts, shares,
                        ticker_prices, effective_fees, buy_quantities)
                )
            ]

            return RebalanceResponse(results=results, total_fees=total_fees, change=change)
        finally:
            dur_hist.record(time.perf_counter() - _start, {"algorithm": algorithm})
            ticker_hist.record(len(request.assets))
