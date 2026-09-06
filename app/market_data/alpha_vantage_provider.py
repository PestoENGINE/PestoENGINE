"""Market data price provider backed by Alpha Vantage Global Quote API."""

from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from app.core.exceptions import MarketDataError
from app.core.http import provider_get, retry_pause, retryable, safe_error
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.quote import MarketQuote, normalize_currency

_BASE_URL = "https://www.alphavantage.co/query"
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class AlphaVantageProvider(AbstractMarketDataProvider):
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        max_age_days: int = 7,
        timeout: float = 10,
    ) -> None:
        if not api_key:
            raise ValueError("AlphaVantageProvider requires a non-empty api_key")
        self._api_key = api_key
        self._client = client
        self._max_age_days = max_age_days
        self._timeout = timeout

    def get_quotes(
        self,
        tickers: list[str],
        *,
        currency_hints: dict[str, str] | None = None,
    ) -> dict[str, MarketQuote]:
        hints = currency_hints or {}
        missing = next((ticker for ticker in tickers if not hints.get(ticker)), None)
        if missing is not None:
            # GLOBAL_QUOTE does not return a quote currency. Require explicit
            # metadata (normally round-tripped from SYMBOL_SEARCH) instead of
            # guessing from the ticker or portfolio base currency.
            raise MarketDataError(
                f"Currency metadata is required for '{missing}' when using "
                "Alpha Vantage. Select the ticker from search first."
            )
        return {
            ticker: self._fetch_single(ticker, normalize_currency(hints[ticker]))
            for ticker in dict.fromkeys(tickers)
        }

    def _fetch_single(self, ticker: str, currency: str) -> MarketQuote:
        last_err: str | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                r = provider_get(
                    self._client,
                    _BASE_URL,
                    params={"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": self._api_key},
                    timeout=self._timeout,
                )
                r.raise_for_status()
                body = r.json()
                if not isinstance(body, dict):
                    raise ValueError("Expected an object")
                # Rate-limit / quota: body contains Note or Information instead of Global Quote.
                # No retry — additional requests would worsen quota consumption.
                if "Note" in body or "Information" in body:
                    raise MarketDataError(f"Alpha Vantage rate limit hit fetching '{ticker}'.")
                quote = body.get("Global Quote") or {}
                if not isinstance(quote, dict):
                    raise ValueError("Expected a quote object")
                price_str = quote.get("05. price")
                if not price_str:
                    raise MarketDataError(f"No price returned by Alpha Vantage for '{ticker}'")
                if not isinstance(price_str, str):
                    raise ValueError("Alpha Vantage price must be a string")
                result = MarketQuote(
                    price=Decimal(price_str),
                    currency=currency,
                    as_of=date.fromisoformat(quote["07. latest trading day"]),
                )
                result.assert_fresh(self._max_age_days)
                return result
            except MarketDataError:
                raise
            except (httpx.HTTPError, InvalidOperation, ValueError, KeyError, TypeError) as exc:
                last_err = safe_error(exc)
                if not retryable(exc) or attempt == _MAX_RETRIES:
                    break
                retry_pause(_RETRY_DELAY)
        raise MarketDataError(
            f"Could not fetch price for '{ticker}' from Alpha Vantage after "
            f"{attempt} attempts. Last error: {last_err}"
        )
