"""FastAPI application entry point."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.resources import AppResources
from app.api.v1.routes import config, health, rebalance, tickers
from app.core.config import Settings, get_settings, request_settings
from app.core.exceptions import (
    CacheUnavailableError,
    MarketDataError,
    cache_unavailable_handler,
    market_data_error_handler,
)
from app.core.log_config import setup_logging

_access_log = logging.getLogger("pestoengine.access")


class _AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            ms = (time.perf_counter() - start) * 1000
            client = f"{request.client.host}:{request.client.port}" if request.client else "-"
            _access_log.info(
                "%s %s %d %.0fms",
                request.method,
                request.url.path,
                status_code,
                ms,
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "http_duration_ms": round(ms, 1),
                    "http_client": client,
                    "http_user_agent": request.headers.get("user-agent", "-"),
                    "http_version": request.scope.get("http_version", "1.1"),
                },
            )


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class _RuntimeContextMiddleware:
    """Set validation settings and trace with the SDK owned by this lifespan."""

    def __init__(self, app) -> None:
        self.app = app
        self._resources = None
        self._traced = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        resources = scope["app"].state.resources
        if resources is not self._resources:
            self._resources = resources
            self._traced = self.app
            if resources.tracer_provider is not None:
                from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

                self._traced = OpenTelemetryMiddleware(
                    self.app,
                    meter_provider=resources.meter_provider,
                    tracer_provider=resources.tracer_provider,
                )
        token = request_settings.set(resources.settings)
        try:
            await self._traced(scope, receive, send)
        finally:
            request_settings.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        redactor = setup_logging(settings)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        resources = AppResources(settings)
        application.state.resources = resources
        handler = None
        try:
            if resources.logger_provider is not None:
                from opentelemetry.instrumentation.logging.handler import LoggingHandler

                handler = LoggingHandler(
                    level=logging.NOTSET, logger_provider=resources.logger_provider
                )
                handler.addFilter(redactor)
                logging.getLogger().addHandler(handler)
            yield
        finally:
            if resources.pending_work:
                await asyncio.gather(*resources.pending_work, return_exceptions=True)
            if handler is not None:
                logging.getLogger().removeHandler(handler)
                handler.close()
            await asyncio.to_thread(resources.close)
            application.state.resources = None

    application = FastAPI(
        title="PestoENGINE API",
        version="2.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.fastapi_docs else None,
        redoc_url="/redoc" if settings.fastapi_docs else None,
        openapi_url="/openapi.json" if settings.fastapi_docs else None,
    )
    application.state.resources = None
    # Starlette is LIFO: CORS and security wrap the rate limiter, including 429s.
    if settings.rate_limit_providers_per_min is not None:
        from app.rate_limit.middleware import RateLimitMiddleware

        application.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_providers_per_min)
    if settings.trusted_proxies:
        from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

        application.add_middleware(
            ProxyHeadersMiddleware,
            trusted_hosts=[h.strip() for h in settings.trusted_proxies.split(",") if h.strip()],
        )
    origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Retry-After"],
        )
    application.add_middleware(_SecurityHeadersMiddleware)
    application.add_middleware(_AccessLogMiddleware)
    application.add_middleware(_RuntimeContextMiddleware)
    application.add_exception_handler(MarketDataError, market_data_error_handler)
    application.add_exception_handler(CacheUnavailableError, cache_unavailable_handler)
    for module in (config, health, rebalance, tickers):
        application.include_router(module.router, prefix="/v1")
    _mount_ui(application, Path(__file__).resolve().parent.parent / "ui" / "dist")
    return application


def _mount_ui(application: FastAPI, ui_dist: Path) -> None:
    if ui_dist.exists():
        application.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")


app = create_app()
