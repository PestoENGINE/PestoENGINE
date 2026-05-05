"""Yahoo Finance market data provider using direct HTTP calls (no yfinance)."""

import logging
import time

import httpx

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider

logger = logging.getLogger(__name__)

_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
_PARAMS = {"interval": "1d", "range": "1d"}
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_RETRIES = 3
_DELAY = 1.0


def _fetch_single(ticker: str) -> float:
    last_error: str | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(
                _URL.format(ticker=ticker),
                params=_PARAMS,
                headers=_HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            if closes:
                return float(closes[-1])
            last_error = f"Empty close data for '{ticker}'."
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Attempt %d/%d failed for '%s': %s",
                attempt, _RETRIES, ticker, exc,
            )
        if attempt < _RETRIES:
            time.sleep(_DELAY)
    raise MarketDataError(
        f"Could not fetch price for '{ticker}' after {_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


class YahooFinanceProvider(AbstractMarketDataProvider):
    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        if not tickers:
            raise ValueError("Ticker list cannot be empty.")
        logger.info("Fetching prices for: %s", tickers)
        prices = {ticker: _fetch_single(ticker) for ticker in tickers}
        logger.info("Prices fetched: %s", prices)
        return prices
