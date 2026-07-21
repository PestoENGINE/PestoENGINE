# app/api/v1/routes/tickers.py
"""GET /v1/tickers/search endpoint — parallel multi-provider search."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_search_providers
from app.market_data.base import AbstractTickerSearchProvider
from app.schemas.ticker import TickerResult, TickerSearchResponse

router = APIRouter(tags=["tickers"])
logger = logging.getLogger(__name__)


@router.api_route("/tickers/search", methods=["GET", "HEAD"], response_model=TickerSearchResponse)
async def search_tickers(
    q: str = Query(..., min_length=2),
    search_providers: list[AbstractTickerSearchProvider] = Depends(get_search_providers),
) -> TickerSearchResponse:
    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, p.search, q) for p in search_providers]
    results_per_provider = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[TickerResult] = []
    all_failed = True
    for results in results_per_provider:
        if isinstance(results, Exception):
            logger.warning("Search provider failed: %s", results)
            continue
        all_failed = False
        for r in results:
            merged.append(TickerResult(
                ticker=r["symbol"],
                name=r["name"],
                exchange=r["exchange"],
                type=r["type"],
                provider=r["provider"],
                currency=r.get("currency"),
            ))

    if all_failed and search_providers:
        raise HTTPException(status_code=503, detail="Market data unavailable")

    return TickerSearchResponse(results=merged)
