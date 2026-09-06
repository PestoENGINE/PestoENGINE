# app/api/v1/routes/tickers.py
"""GET /v1/tickers/search endpoint — parallel multi-provider search."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_resources, get_search_providers
from app.api.resources import AppResources
from app.api.work import run_provider_work
from app.market_data.base import AbstractTickerSearchProvider
from app.schemas.ticker import TickerResult, TickerSearchResponse

router = APIRouter(tags=["tickers"])
logger = logging.getLogger(__name__)


@router.api_route("/tickers/search", methods=["GET", "HEAD"], response_model=TickerSearchResponse)
async def search_tickers(
    q: str = Query(..., min_length=2, max_length=64),
    resources: AppResources = Depends(get_resources),
    search_providers: list[AbstractTickerSearchProvider] = Depends(get_search_providers),
) -> TickerSearchResponse:
    q = q.strip()
    if len(q) < 2 or any(ord(c) < 32 or ord(c) == 127 for c in q):
        raise HTTPException(422, "Search query must contain 2 to 64 printable characters")
    tasks = [run_provider_work(resources, p.search, q) for p in search_providers]
    results_per_provider = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[TickerResult] = []
    all_failed = True
    for results in results_per_provider:
        if isinstance(results, Exception):
            logger.warning("Search provider failed: %s", results)
            continue
        all_failed = False
        for r in results:
            merged.append(
                TickerResult(
                    ticker=r["symbol"],
                    name=r["name"],
                    exchange=r["exchange"],
                    type=r["type"],
                    provider=r["provider"],
                    currency=r.get("currency"),
                )
            )

    if all_failed and search_providers:
        raise HTTPException(status_code=503, detail="Market data unavailable")

    return TickerSearchResponse(results=merged)
