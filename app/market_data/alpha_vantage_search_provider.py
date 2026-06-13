"""Ticker search provider backed by Alpha Vantage Symbol Search API."""

import logging

import httpx

from app.market_data.base import AbstractTickerSearchProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.alphavantage.co/query"

# AV type strings -> canonical type (Yahoo vocabulary)
_TYPE_MAP = {
    "Equity": "EQUITY",
    "ETF": "ETF",
    "Mutual Fund": "MUTUALFUND",
    "Currency": "CURRENCY",
    "Cryptocurrency": "CRYPTOCURRENCY",
}


class AlphaVantageSearchProvider(AbstractTickerSearchProvider):
    LABEL = "AV"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("AlphaVantageSearchProvider requires a non-empty api_key")
        self._api_key = api_key

    def search(self, q: str) -> list[dict]:
        try:
            r = httpx.get(
                _BASE_URL,
                params={"function": "SYMBOL_SEARCH", "keywords": q, "apikey": self._api_key},
                timeout=10.0,
            )
            r.raise_for_status()
            body = r.json()
        except Exception:
            logger.warning("Alpha Vantage search failed for query %r", q)
            return []

        if "bestMatches" not in body:
            # Rate limit (Note/Information key present) or unexpected response — degrade silently
            return []

        results = []
        for m in body["bestMatches"]:
            mapped_type = _TYPE_MAP.get(m.get("3. type", ""))
            if not mapped_type:
                continue
            results.append({
                "symbol": m["1. symbol"],
                "name": f"{self.LABEL} · {m['2. name']}",
                # Market label: AV exposes no exchange display name, so the region
                # is the closest human-readable value (e.g. "United States").
                "exchange": m.get("4. region", ""),
                "type": mapped_type,
                "provider": "alphavantage",
            })
        return results
