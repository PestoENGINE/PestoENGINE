"""Yahoo Finance market data provider using direct HTTP calls (no yfinance)."""

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

from app.core.exceptions import MarketDataError
from app.core.http import provider_get, retry_pause, retryable, safe_error
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.quote import MarketQuote

logger = logging.getLogger(__name__)

_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
_PARAMS = {"interval": "1d", "range": "1d"}
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_RETRIES = 3
_DELAY = 1.0


def _fetch_single(
    ticker: str, *, client: httpx.Client | None = None, max_age_days: int = 7, timeout: float = 10
) -> MarketQuote:
    for attempt in range(1, _RETRIES + 1):
        try:
            response = provider_get(
                client,
                _URL.format(ticker=quote(ticker, safe="")),
                params=_PARAMS,
                headers=_HEADERS,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json(parse_float=Decimal)["chart"]["result"][0]
            currency = result["meta"].get("currency")
            if not currency:
                raise ValueError("Currency missing from Yahoo quote")
            closes = result["indicators"]["quote"][0]["close"]
            index = next((i for i in range(len(closes) - 1, -1, -1) if closes[i] is not None), None)
            if index is None:
                raise ValueError("Empty close data")
            observation = datetime.fromtimestamp(float(result["timestamp"][index]), UTC).date()
            market_quote = MarketQuote(Decimal(str(closes[index])), currency, observation)
            market_quote.assert_fresh(max_age_days)
            return market_quote
        except (
            httpx.HTTPError,
            InvalidOperation,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            OverflowError,
            OSError,
        ) as exc:
            error = safe_error(exc)
            logger.warning(
                "Yahoo fetch attempt %d/%d failed for '%s': %s", attempt, _RETRIES, ticker, error
            )
            if not retryable(exc) or attempt == _RETRIES:
                break
            retry_pause(_DELAY)
    raise MarketDataError(
        f"Could not fetch price for '{ticker}' after {attempt} attempts. Last error: {error}"
    )


class YahooFinanceProvider(AbstractMarketDataProvider):
    def __init__(
        self, *, client: httpx.Client | None = None, max_age_days: int = 7, timeout: float = 10
    ) -> None:
        self._client = client
        self._max_age_days = max_age_days
        self._timeout = timeout

    def get_quotes(
        self,
        tickers: list[str],
        *,
        currency_hints: dict[str, str] | None = None,
    ) -> dict[str, MarketQuote]:
        if not tickers:
            raise ValueError("Ticker list cannot be empty.")
        logger.info("Fetching quotes for: %s", tickers)
        quotes = {
            ticker: _fetch_single(
                ticker, client=self._client, max_age_days=self._max_age_days, timeout=self._timeout
            )
            for ticker in dict.fromkeys(tickers)
        }
        logger.info("Quotes fetched for: %s", list(quotes))
        return quotes
