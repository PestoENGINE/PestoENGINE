"""Ticker search provider backed by Yahoo Finance search API."""

import logging

import httpx

from app.market_data.base import AbstractTickerSearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


class YahooTickerSearchProvider(AbstractTickerSearchProvider):
    LABEL = "YF"
    _ALLOWED_TYPES = {"EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY", "CURRENCY"}

    def search(self, q: str) -> list[dict]:
        r = httpx.get(
            _SEARCH_URL,
            params={"q": q, "lang": "en-US", "region": "US", "quotesCount": 10, "newsCount": 0},
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        raw = r.json().get("quotes") or []
        results = []
        for item in raw:
            qt = item.get("quoteType")
            if qt not in self._ALLOWED_TYPES:
                continue
            name = item.get("shortname") or item.get("longname") or ""
            results.append({
                "symbol": item["symbol"],
                "name": f"{self.LABEL} · {name}",
                # Human-readable market label (e.g. "XETRA", "Milan", "NASDAQ").
                # exchDisp is the display name; fall back to the raw code.
                "exchange": item.get("exchDisp") or item.get("exchange", ""),
                "type": qt,
                "provider": "yahoo",
            })
        return results
