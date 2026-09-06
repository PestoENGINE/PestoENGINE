"""POST /v1/rebalance endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_fx_provider, get_registry, get_resources
from app.api.resources import AppResources
from app.api.work import run_provider_work
from app.core.exceptions import CacheUnavailableError, MarketDataError
from app.fx.ecb_provider import EcbFxProvider
from app.market_data.provider_registry import ProviderRegistry
from app.schemas.request import RebalanceRequest
from app.schemas.result import RebalanceResponse
from app.services.rebalance_service import run_rebalance

router = APIRouter(tags=["rebalance"])
logger = logging.getLogger(__name__)


@router.post("/rebalance", response_model=RebalanceResponse)
async def rebalance(
    payload: RebalanceRequest,
    resources: AppResources = Depends(get_resources),
    registry: ProviderRegistry = Depends(get_registry),
    fx_provider: EcbFxProvider = Depends(get_fx_provider),
) -> RebalanceResponse:
    try:
        return await run_provider_work(
            resources,
            run_rebalance,
            payload,
            registry,
            fx_provider,
            meter_provider=resources.meter_provider,
            tracer_provider=resources.tracer_provider,
        )
    except (MarketDataError, CacheUnavailableError, HTTPException):
        raise
    except Exception:
        logger.exception("Unexpected error in /rebalance")
        raise
