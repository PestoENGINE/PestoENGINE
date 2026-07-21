"""Yahoo Finance market data provider using direct HTTP calls (no yfinance)."""

import logging
import time
from decimal import Decimal

import httpx

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.quote import MarketQuote

logger = logging.getLogger(__name__)

_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
_PARAMS = {"interval": "1d", "range": "1d"}
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_RETRIES = 3
_DELAY = 1.0


def _fetch_single(ticker: str) -> MarketQuote:
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
            # Parse JSON numbers directly as Decimal so provider precision is
            # not routed through a binary float before entering MarketQuote.
            result = r.json(parse_float=Decimal)["chart"]["result"][0]
            meta = result.get("meta") or {}
            currency = meta.get("currency")
            if not currency:
                raise ValueError(f"Currency missing from Yahoo quote for '{ticker}'.")
            closes = result["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            if closes:
                return MarketQuote(
                    price=Decimal(str(closes[-1])),
                    currency=str(currency),
                )
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
    def get_quotes(
        self,
        tickers: list[str],
        *,
        currency_hints: dict[str, str] | None = None,
    ) -> dict[str, MarketQuote]:
        if not tickers:
            raise ValueError("Ticker list cannot be empty.")
        logger.info("Fetching quotes for: %s", tickers)
        quotes = {ticker: _fetch_single(ticker) for ticker in tickers}
        logger.info("Quotes fetched for: %s", list(quotes))
        return quotes
