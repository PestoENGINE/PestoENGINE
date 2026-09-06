"""Ticker search provider backed by Yahoo Finance search API."""

import logging

import httpx

from app.core.exceptions import MarketDataError
from app.core.http import provider_get, safe_error
from app.market_data.base import AbstractTickerSearchProvider, SearchResult
from app.market_data.quote import try_normalize_currency

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


class YahooTickerSearchProvider(AbstractTickerSearchProvider):
    LABEL = "YF"
    _ALLOWED_TYPES = {"EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY", "CURRENCY"}

    def __init__(self, *, client: httpx.Client | None = None, timeout: float = 10) -> None:
        self._client = client
        self._timeout = timeout

    def search(self, q: str) -> list[SearchResult]:
        try:
            r = provider_get(
                self._client,
                _SEARCH_URL,
                params={"q": q, "lang": "en-US", "region": "US", "quotesCount": 10, "newsCount": 0},
                headers=_HEADERS,
                timeout=self._timeout,
            )
            r.raise_for_status()
            body = r.json()
            if not isinstance(body, dict) or not isinstance(body.get("quotes"), list):
                raise ValueError("Malformed Yahoo search response")
            raw = body["quotes"]
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Yahoo search unavailable: {safe_error(exc)}") from exc
        results = []
        for item in raw:
            if not isinstance(item, dict):
                raise MarketDataError("Malformed Yahoo search entry")
            if not isinstance(item.get("symbol"), str) or not item["symbol"].strip():
                continue
            qt = item.get("quoteType")
            if qt not in self._ALLOWED_TYPES:
                continue
            name = item.get("shortname") or item.get("longname") or ""
            if not isinstance(name, str):
                continue
            results.append(
                {
                    "symbol": item["symbol"],
                    "name": f"{self.LABEL} · {name}",
                    # Human-readable market label (e.g. "XETRA", "Milan", "NASDAQ").
                    # exchDisp is the display name; fall back to the raw code.
                    "exchange": str(item.get("exchDisp") or item.get("exchange") or ""),
                    "type": qt,
                    "provider": "yahoo",
                    "currency": try_normalize_currency(item.get("currency")),
                }
            )
        return results
