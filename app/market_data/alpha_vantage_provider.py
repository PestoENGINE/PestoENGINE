"""Market data price provider backed by Alpha Vantage Global Quote API."""

import time

import httpx

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider

_BASE_URL = "https://www.alphavantage.co/query"
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class AlphaVantageProvider(AbstractMarketDataProvider):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("AlphaVantageProvider requires a non-empty api_key")
        self._api_key = api_key

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        return {t: self._fetch_single(t) for t in tickers}

    def _fetch_single(self, ticker: str) -> float:
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
                return float(price_str)
            except MarketDataError:
                raise
            except (httpx.HTTPError, ValueError) as e:
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
