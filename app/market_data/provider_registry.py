"""Registry that dispatches price fetches across multiple market data providers."""

from opentelemetry import metrics as _metrics

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.quote import MarketQuote


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

    def get_quotes_for_assets(self, assets: list) -> dict[str, MarketQuote]:
        """Return a complete currency-aware quote for every asset.

        Args:
            assets: objects with .ticker, .provider and optional .currency.
        """
        quotes: dict[str, MarketQuote] = {}

        # --- Explicit provider assets: batch by provider, fail-fast ---
        by_provider: dict[str, list] = {}
        fallback_assets: list = []

        for asset in assets:
            if asset.provider:
                by_provider.setdefault(asset.provider, []).append(asset)
            else:
                fallback_assets.append(asset)

        for pid, provider_assets in by_provider.items():
            if pid not in self._providers:
                raise MarketDataError(f"Provider '{pid}' is not configured.")
            tickers = [asset.ticker for asset in provider_assets]
            currency_hints = {
                asset.ticker: asset.currency
                for asset in provider_assets
                if asset.currency
            }
            try:
                quotes.update(self._providers[pid].get_quotes(
                    tickers,
                    currency_hints=currency_hints,
                ))
            except MarketDataError as e:
                self._errors.add(1, {"provider": pid, "error_type": "explicit"})
                raise MarketDataError(f"[{pid}] {e}") from e

        # --- Fallback chain: per-ticker, first provider to return wins ---
        for asset in fallback_assets:
            ticker = asset.ticker
            resolved = False
            currency_hints = {ticker: asset.currency} if asset.currency else {}
            for pid in self._fallback_order:
                try:
                    quote = self._providers[pid].get_quotes(
                        [ticker],
                        currency_hints=currency_hints,
                    )[ticker]
                    quotes[ticker] = quote
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

        return quotes
