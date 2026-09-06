"""Custom exception types and FastAPI exception handlers."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class MarketDataError(RuntimeError):
    """Raised when market prices cannot be retrieved."""


class ProviderDeadlineError(MarketDataError):
    """Provider work exhausted the request budget."""


async def market_data_error_handler(request: Request, exc: MarketDataError) -> JSONResponse:
    logger.warning("MarketDataError on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


class CacheUnavailableError(RuntimeError):
    """The configured shared cache is unavailable."""


async def cache_unavailable_handler(request: Request, exc: CacheUnavailableError) -> JSONResponse:
    logger.warning("Configured cache unavailable on %s", request.url.path)
    return JSONResponse(status_code=503, content={"detail": "Cache unavailable"})
