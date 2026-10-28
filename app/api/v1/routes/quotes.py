"""POST /v1/quotes endpoint: base-currency prices for the browser engine."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_fx_provider, get_registry, get_resources
from app.api.resources import AppResources
from app.api.work import run_provider_work
from app.core.exceptions import CacheUnavailableError, MarketDataError
from app.fx.ecb_provider import EcbFxProvider
from app.market_data.provider_registry import ProviderRegistry
from app.schemas.request import QuotesRequest
from app.schemas.result import QuotesResponse
from app.services.rebalance_service import run_quotes

router = APIRouter(tags=["rebalance"])
logger = logging.getLogger(__name__)


@router.post("/quotes", response_model=QuotesResponse)
async def quotes(
    payload: QuotesRequest,
    resources: AppResources = Depends(get_resources),
    registry: ProviderRegistry = Depends(get_registry),
    fx_provider: EcbFxProvider = Depends(get_fx_provider),
) -> QuotesResponse:
    try:
        return await run_provider_work(resources, run_quotes, payload, registry, fx_provider)
    except (MarketDataError, CacheUnavailableError, HTTPException):
        raise
    except Exception:
        logger.exception("Unexpected error in /quotes")
        raise
