# app/schemas/ticker.py
"""Pydantic v2 schemas for GET /v1/tickers/search."""

from pydantic import BaseModel


class TickerResult(BaseModel):
    ticker: str
    name: str
    exchange: str
    type: str


class TickerSearchResponse(BaseModel):
    results: list[TickerResult]
