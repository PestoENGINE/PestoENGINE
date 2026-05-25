"""Rate limiting middleware for provider-heavy endpoints."""

import logging
import time

from opentelemetry import metrics as _metrics
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.rate_limit.base import AbstractRateLimitStore

_logger = logging.getLogger("pestoengine.rate_limit")

_RATE_LIMITED_PATHS = frozenset({"/v1/rebalance", "/v1/tickers/search"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        store: AbstractRateLimitStore,
        limit: int,
        meter_provider: _metrics.MeterProvider | None = None,
    ) -> None:
        super().__init__(app)
        self.store = store
        self.limit = limit
        mp = meter_provider if meter_provider is not None else _metrics.get_meter_provider()
        meter = mp.get_meter("pestoengine.rate_limit")
        self._counter = meter.create_counter(
            "pestoengine_rate_limit_total",
            unit="requests",
            description="Rate limit decisions by outcome and endpoint",
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path not in _RATE_LIMITED_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = int(time.time())
        epoch_minute = now // 60
        key = f"rl:providers:{ip}:{epoch_minute}"
        endpoint = "rebalance" if "/rebalance" in request.url.path else "search"

        try:
            count = self.store.increment(key, window_seconds=60)
        except Exception as exc:
            # Store unavailable; fail-open to preserve service availability.
            # A deterrent limiter must never cause a production outage.
            _logger.warning("Rate limit store error, failing open: %s", exc)
            self._counter.add(1, {"outcome": "allowed", "endpoint": endpoint})
            return await call_next(request)

        if count > self.limit:
            seconds_remaining = 60 - (now % 60)
            self._counter.add(1, {"outcome": "denied", "endpoint": endpoint})
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in {seconds_remaining} seconds."},
                headers={"Retry-After": str(seconds_remaining)},
            )

        self._counter.add(1, {"outcome": "allowed", "endpoint": endpoint})
        return await call_next(request)
