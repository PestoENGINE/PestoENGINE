"""GET|HEAD /v1/health liveness probe and GET|HEAD /v1/ready readiness probe."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import RedisError

from app.api.deps import get_resources
from app.api.resources import AppResources

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@router.api_route("/ready", methods=["GET", "HEAD"], include_in_schema=False)
def ready(resources: AppResources = Depends(get_resources)) -> JSONResponse:
    if resources.redis_client is not None:
        try:
            resources.redis_client.ping()
        except RedisError:
            logger.warning("Readiness check failed: Redis unavailable")
            return JSONResponse(status_code=503, content={"status": "redis_unavailable"})
    return JSONResponse(content={"status": "ok"})
