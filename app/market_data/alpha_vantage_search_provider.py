"""Ticker search provider backed by Alpha Vantage Symbol Search API."""

import logging

import httpx

from app.core.exceptions import MarketDataError
from app.core.http import provider_get, safe_error
from app.market_data.base import AbstractTickerSearchProvider, SearchResult
from app.market_data.quote import try_normalize_currency

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

    def __init__(
        self, api_key: str, *, client: httpx.Client | None = None, timeout: float = 10
    ) -> None:
        if not api_key:
            raise ValueError("AlphaVantageSearchProvider requires a non-empty api_key")
        self._api_key = api_key
        self._client = client
        self._timeout = timeout

    def search(self, q: str) -> list[SearchResult]:
        try:
            r = provider_get(
                self._client,
                _BASE_URL,
                params={"function": "SYMBOL_SEARCH", "keywords": q, "apikey": self._api_key},
                timeout=self._timeout,
            )
            r.raise_for_status()
            body = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Alpha Vantage search unavailable: {safe_error(exc)}") from exc
        if not isinstance(body, dict) or not isinstance(body.get("bestMatches"), list):
            raise MarketDataError("Alpha Vantage search unavailable or malformed response")

        results = []
        for m in body["bestMatches"]:
            if not isinstance(m, dict):
                raise MarketDataError("Malformed Alpha Vantage search entry")
            if any(
                not isinstance(m.get(k), str) or not m[k].strip() for k in ("1. symbol", "2. name")
            ):
                continue
            mapped_type = _TYPE_MAP.get(m.get("3. type", ""))
            if not mapped_type:
                continue
            results.append(
                {
                    "symbol": m["1. symbol"],
                    "name": f"{self.LABEL} · {m['2. name']}",
                    # Market label: AV exposes no exchange display name, so the region
                    # is the closest human-readable value (e.g. "United States").
                    "exchange": str(m.get("4. region") or ""),
                    "type": mapped_type,
                    "provider": "alphavantage",
                    "currency": try_normalize_currency(m.get("8. currency")),
                }
            )
        return results
