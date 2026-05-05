"""POST /v1/rebalance endpoint."""

import asyncio
import logging

from fastapi import APIRouter, Depends

from app.api.deps import get_market_provider
from app.core.exceptions import MarketDataError
from app.market_data.base import AbstractMarketDataProvider
from app.schemas.request import RebalanceRequest
from app.schemas.result import RebalanceResponse
from app.services.rebalance_service import run_rebalance

router = APIRouter(tags=["rebalance"])
logger = logging.getLogger(__name__)


@router.post("/rebalance", response_model=RebalanceResponse)
async def rebalance(
    payload: RebalanceRequest,
    provider: AbstractMarketDataProvider = Depends(get_market_provider),
) -> RebalanceResponse:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, run_rebalance, payload, provider)
    except MarketDataError:
        raise
    except Exception:
        logger.exception("Unexpected error in /rebalance")
        raise
