"""Registry that dispatches price fetches across multiple market data providers."""

from collections.abc import Sequence

from opentelemetry import metrics as _metrics

from app.core.exceptions import MarketDataError, ProviderDeadlineError
from app.market_data.base import AbstractMarketDataProvider, AssetReference
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

    def get_quotes_for_assets(self, assets: Sequence[AssetReference]) -> list[MarketQuote]:
        """Return quotes aligned with input rows, preserving provider/currency identity."""
        quotes: dict[int, MarketQuote] = {}
        groups: dict[tuple[str, str | None], list[int]] = {}
        for i, asset in enumerate(assets):
            if asset.provider:
                groups.setdefault((asset.provider, asset.currency), []).append(i)
        for (pid, hint), indices in groups.items():
            if pid not in self._providers:
                raise MarketDataError(f"Provider '{pid}' is not configured.")
            tickers = list(dict.fromkeys(assets[i].ticker for i in indices))
            try:
                batch = self._providers[pid].get_quotes(
                    tickers,
                    currency_hints={t: hint for t in tickers} if hint else {},
                )
                if any(t not in batch for t in tickers):
                    raise MarketDataError("Provider returned incomplete quotes")
                for i in indices:
                    quotes[i] = batch[assets[i].ticker]
            except ProviderDeadlineError:
                raise
            except MarketDataError as exc:
                self._errors.add(1, {"provider": pid, "error_type": "explicit"})
                raise MarketDataError(f"[{pid}] {exc}") from exc
        for i, asset in enumerate(assets):
            if asset.provider:
                continue
            for pid in self._fallback_order:
                try:
                    batch = self._providers[pid].get_quotes(
                        [asset.ticker],
                        currency_hints={asset.ticker: asset.currency} if asset.currency else {},
                    )
                    if asset.ticker not in batch:
                        raise MarketDataError("Provider returned incomplete quotes")
                    quotes[i] = batch[asset.ticker]
                    break
                except ProviderDeadlineError:
                    raise
                except MarketDataError:
                    self._errors.add(1, {"provider": pid, "error_type": "fallback"})
            else:
                raise MarketDataError(
                    f"Ticker '{asset.ticker}' not found in any configured provider "
                    f"({', '.join(self._fallback_order)})."
                )
        return [quotes[i] for i in range(len(assets))]
