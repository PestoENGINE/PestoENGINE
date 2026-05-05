"""Custom exception types and FastAPI exception handlers."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class MarketDataError(RuntimeError):
    """Raised when market prices cannot be retrieved."""


async def market_data_error_handler(request: Request, exc: MarketDataError) -> JSONResponse:
    logger.warning("MarketDataError on %s: %s", request.url, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})
