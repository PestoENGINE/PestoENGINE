# app/schemas/ticker.py
"""Pydantic v2 schemas for GET /v1/tickers/search."""

from pydantic import BaseModel


class TickerResult(BaseModel):
    ticker: str
    name: str       # includes provider label prefix e.g. "YF · Vanguard FTSE..."
    exchange: str
    type: str
    provider: str   # provider ID for round-trip to /v1/rebalance


class TickerSearchResponse(BaseModel):
    results: list[TickerResult]
