"""yfinance-backed market data provider."""

import logging
import time

import pandas as pd
import yfinance as yf

from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider

logger = logging.getLogger(__name__)

_FALLBACK_RETRIES = 3
_FALLBACK_DELAY = 1.0


def _fetch_single(ticker: str) -> float:
    """Fetch the latest closing price for a single ticker with retries.

    Used as a fallback when the batch download fails for a specific symbol.

    Args:
        ticker: A Yahoo Finance ticker symbol.

    Returns:
        Latest closing price as a float.

    Raises:
        MarketDataError: If the price cannot be fetched after all retries.
    """
    last_error: str | None = None
    for attempt in range(1, _FALLBACK_RETRIES + 1):
        try:
            history = yf.Ticker(ticker).history(period="1d")
            if not history.empty:
                return float(history["Close"].iloc[-1])
            logger.warning(
                "Attempt %d/%d: empty history for '%s'.",
                attempt, _FALLBACK_RETRIES, ticker,
            )
            last_error = f"Empty price history for ticker '{ticker}'."
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Attempt %d/%d failed for '%s': %s",
                attempt, _FALLBACK_RETRIES, ticker, exc,
            )
        if attempt < _FALLBACK_RETRIES:
            time.sleep(_FALLBACK_DELAY)

    raise MarketDataError(
        f"Could not fetch price for '{ticker}' after {_FALLBACK_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


class YFinanceProvider(AbstractMarketDataProvider):
    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Fetch the latest closing price for a list of ticker symbols.

        Attempts a single batch yf.download() call for efficiency. Any ticker
        whose result is empty or NaN (e.g. due to a transient SQLite cache lock in
        yfinance >= 1.x) is retried individually via yf.Ticker.history().

        Args:
            tickers: Non-empty list of ticker symbols (e.g. ["VWCE.DE", "VAGF.DE"]).

        Returns:
            A dict mapping each ticker symbol to its latest closing price as a float.

        Raises:
            ValueError: If tickers is empty.
            MarketDataError: If any ticker's price cannot be retrieved.
        """
        if not tickers:
            raise ValueError("Ticker list cannot be empty.")

        logger.info("Fetching prices for: %s", tickers)

        prices: dict[str, float] = {}
        fallback_tickers: list[str] = []

        try:
            raw = yf.download(tickers, period="1d", auto_adjust=True, progress=False)

            if not raw.empty:
                close = raw["Close"]

                if isinstance(close, pd.Series):
                    close = close.to_frame(name=tickers[0])

                for ticker in tickers:
                    if ticker in close.columns:
                        series = close[ticker].dropna()
                        if not series.empty:
                            prices[ticker] = float(series.iloc[-1])
                            continue
                    logger.warning(
                        "Batch download returned no data for '%s', falling back to "
                        "individual fetch.",
                        ticker,
                    )
                    fallback_tickers.append(ticker)
            else:
                logger.warning(
                    "Batch download returned empty result, falling back to individual "
                    "fetches for all tickers."
                )
                fallback_tickers = list(tickers)

        except Exception as exc:
            logger.warning(
                "Batch download failed (%s), falling back to individual fetches.", exc
            )
            fallback_tickers = [t for t in tickers if t not in prices]

        for ticker in fallback_tickers:
            prices[ticker] = _fetch_single(ticker)

        logger.info("Prices fetched: %s", prices)
        return prices
