"""GET /v1/health liveness probe and GET /v1/ready readiness probe."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@router.get("/ready", include_in_schema=False)
def ready() -> JSONResponse:
    settings = get_settings()
    if settings.cache_backend == "redis":
        if not settings.redis_url:
            return JSONResponse(status_code=503, content={"status": "redis_url_missing"})
        try:
            import redis
            client = redis.from_url(
                settings.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
        except Exception as exc:
            logger.warning("Readiness check failed: %s", exc)
            return JSONResponse(status_code=503, content={"status": "redis_unavailable"})
    return JSONResponse(content={"status": "ok"})
