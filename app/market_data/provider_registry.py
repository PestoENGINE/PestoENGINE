"""Registry that dispatches price fetches across multiple market data providers."""

from opentelemetry import metrics as _metrics

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider


class ProviderRegistry:
    """Routes price fetches to the correct provider per asset.

    Assets with an explicit provider go directly to that provider (fail-fast).
    Assets with provider=None are tried against each provider in fallback_order
    on a per-ticker basis — first provider that returns a price wins.
    """

    def __init__(
        self,
        providers: dict[str, AbstractMarketDataProvider],
        fallback_order: list[str],
        *,
        meter_provider: _metrics.MeterProvider | None = None,
    ) -> None:
        self._providers = providers
        self._fallback_order = fallback_order
        mp = meter_provider if meter_provider is not None else _metrics.get_meter_provider()
        meter = mp.get_meter("pestoengine.providers")
        self._errors = meter.create_counter(
            "pestoengine_provider_errors_total",
            description="Provider failures during price fetch",
        )

    def get_prices_for_assets(self, assets: list) -> dict[str, float]:
        """Return {ticker: price} for all assets.

        Args:
            assets: objects with .ticker (str) and .provider (str | None).
        """
        prices: dict[str, float] = {}

        # --- Explicit provider assets: batch by provider, fail-fast ---
        by_provider: dict[str, list[str]] = {}
        fallback_tickers: list[str] = []

        for asset in assets:
            if asset.provider:
                by_provider.setdefault(asset.provider, []).append(asset.ticker)
            else:
                fallback_tickers.append(asset.ticker)

        for pid, tickers in by_provider.items():
            if pid not in self._providers:
                raise MarketDataError(f"Provider '{pid}' is not configured.")
            try:
                prices.update(self._providers[pid].get_prices(tickers))
            except MarketDataError as e:
                self._errors.add(1, {"provider": pid, "error_type": "explicit"})
                raise MarketDataError(f"[{pid}] {e}") from e

        # --- Fallback chain: per-ticker, first provider to return wins ---
        for ticker in fallback_tickers:
            resolved = False
            for pid in self._fallback_order:
                try:
                    result = self._providers[pid].get_prices([ticker])
                    prices[ticker] = result[ticker]
                    resolved = True
                    break
                except MarketDataError:
                    self._errors.add(1, {"provider": pid, "error_type": "fallback"})
                    continue
            if not resolved:
                tried = ", ".join(self._fallback_order)
                raise MarketDataError(
                    f"Ticker '{ticker}' not found in any configured provider ({tried})."
                )

        return prices
