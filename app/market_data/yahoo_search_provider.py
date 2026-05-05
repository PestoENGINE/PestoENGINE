"""Ticker search provider backed by Yahoo Finance search API."""

import logging

import httpx

from app.market_data.base import AbstractTickerSearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


class YahooTickerSearchProvider(AbstractTickerSearchProvider):
    def search(self, q: str) -> list[dict]:
        r = httpx.get(
            _SEARCH_URL,
            params={"q": q, "lang": "en-US", "region": "US", "quotesCount": 10, "newsCount": 0},
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("quotes") or []


# --- Fallback: yfinance-based implementation (commented out) ---
# To restore: pip install yfinance, swap class above with this one in deps.py
#
# import yfinance as yf
#
# class YahooTickerSearchProvider(AbstractTickerSearchProvider):
#     def search(self, q: str) -> list[dict]:
#         return yf.Search(q).quotes or []
