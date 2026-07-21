"""Market data price provider backed by Alpha Vantage Global Quote API."""

import time
from decimal import Decimal, InvalidOperation

import httpx

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.quote import MarketQuote, normalize_currency

_BASE_URL = "https://www.alphavantage.co/query"
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class AlphaVantageProvider(AbstractMarketDataProvider):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("AlphaVantageProvider requires a non-empty api_key")
        self._api_key = api_key

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
            for ticker in tickers
        }

    def _fetch_single(self, ticker: str, currency: str) -> MarketQuote:
        last_err: str | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                r = httpx.get(
                    _BASE_URL,
                    params={"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": self._api_key},
                    timeout=10.0,
                )
                r.raise_for_status()
                body = r.json()
                # Rate-limit / quota: body contains Note or Information instead of Global Quote.
                # No retry — additional requests would worsen quota consumption.
                if "Note" in body or "Information" in body:
                    raise MarketDataError(
                        f"Alpha Vantage rate limit hit fetching '{ticker}': "
                        f"{body.get('Note') or body.get('Information')}"
                    )
                quote = body.get("Global Quote") or {}
                price_str = quote.get("05. price")
                if not price_str:
                    raise MarketDataError(
                        f"No price returned by Alpha Vantage for '{ticker}'"
                    )
                if not isinstance(price_str, str):
                    raise ValueError("Alpha Vantage price must be a string")
                return MarketQuote(
                    price=Decimal(price_str),
                    currency=currency,
                )
            except MarketDataError:
                raise
            except (httpx.HTTPError, InvalidOperation, ValueError) as e:
                if isinstance(e, httpx.HTTPStatusError):
                    last_err = f"HTTP {e.response.status_code}"
                else:
                    last_err = type(e).__name__
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
        raise MarketDataError(
            f"Could not fetch price for '{ticker}' from Alpha Vantage after "
            f"{_MAX_RETRIES} attempts. Last error: {last_err}"
        )
