"""Orchestration of the DCA rebalancing flow."""

import time
from decimal import Decimal, localcontext
from functools import lru_cache

from opentelemetry import metrics as _otel_metrics
from opentelemetry import trace as _otel_trace

from app import rebalance
from app.core.exceptions import MarketDataError
from app.fx.ecb_provider import EcbFxProvider
from app.market_data.provider_registry import ProviderRegistry
from app.rebalance.orders import plan_orders
from app.schemas.request import RebalanceRequest
from app.schemas.result import RebalanceResponse

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


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
    fx_provider: EcbFxProvider | None = None,
    *,
    meter_provider: _otel_metrics.MeterProvider | None = None,
    tracer_provider: _otel_trace.TracerProvider | None = None,
) -> RebalanceResponse:
    dur_hist, ticker_hist = _rebalance_instruments(meter_provider)
    algorithm = (
        "fractional"
        if request.fractional_shares
        else ("dp" if request.optimal_redistribute else "greedy")
    )
    _start = time.perf_counter()
    tracer = (
        tracer_provider.get_tracer("pestoengine.rebalance")
        if tracer_provider is not None
        else _tracer
    )
    with (
        localcontext() as context,
        tracer.start_as_current_span(
            "rebalance_compute",
            attributes={
                "rebalance.algorithm": algorithm,
                "rebalance.tickers.count": len(request.assets),
                "rebalance.only_buy": request.only_buy,
                "rebalance.increment": float(request.increment),
            },
        ),
    ):
        context.prec = 128
        try:
            tickers = [a.ticker for a in request.assets]
            desired_pcts = [a.desired_percentage for a in request.assets]
            shares = [a.shares for a in request.assets]

            quotes = registry.get_quotes_for_assets(request.assets)

            base_currency = request.base_currency

            currencies_to_convert = {
                quote.currency for quote in quotes if quote.currency != base_currency
            }
            fx_rates: dict[str, Decimal] = {}
            if currencies_to_convert:
                if fx_provider is None:
                    raise MarketDataError("ECB FX provider is not configured for this rebalance.")
                fx_rates = fx_provider.get_rates(
                    currencies_to_convert,
                    base_currency,
                )
            ticker_prices = [
                quote.price
                if quote.currency == base_currency
                else quote.price * fx_rates[quote.currency]
                for quote in quotes
            ]

            values = [s * p for s, p in zip(shares, ticker_prices)]
            total_value = sum(values)
            current_pcts = [v * _HUNDRED / total_value if total_value else _ZERO for v in values]

            rebalance_amounts = rebalance.calculate_rebalance(
                request.only_buy, request.increment, values, desired_pcts
            )

            plan = plan_orders(
                gaps=rebalance_amounts,
                prices=ticker_prices,
                shares=shares,
                fees=[a.fees for a in request.assets],
                percentage_fees=[a.percentage_fee for a in request.assets],
                increment=request.increment,
                current_percentages=current_pcts,
                desired_percentages=desired_pcts,
                only_buy=request.only_buy,
                fractional=request.fractional_shares,
                optimal=request.optimal_redistribute,
            )
            buy_quantities, effective_fees, change = plan.quantities, plan.fees, plan.change
            total_fees = sum(effective_fees, _ZERO)

            results = [
                {
                    "id": i,
                    "ticker": tickers[i],
                    "current_percentage": current_pcts[i],
                    "desired_percentage": desired_pcts[i],
                    "shares": shares[i],
                    "allocated": buy_quantities[i] * ticker_prices[i],
                    "ticker_price": ticker_prices[i],
                    "quote_as_of": quotes[i].as_of,
                    "fees": (effective_fees[i] if buy_quantities[i] else _ZERO),
                    "buy": buy_quantities[i],
                }
                for i in range(len(tickers))
            ]

            return RebalanceResponse(
                results=results,
                total_fees=total_fees,
                change=change,
                base_currency=base_currency,
                fx_as_of=getattr(fx_rates, "as_of", None),
            )
        finally:
            dur_hist.record(time.perf_counter() - _start, {"algorithm": algorithm})
            ticker_hist.record(len(request.assets))
