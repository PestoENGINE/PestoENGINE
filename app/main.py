"""FastAPI application entry point."""

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

from app.api.v1.routes import health, rebalance, tickers
from app.core.config import get_settings
from app.core.exceptions import MarketDataError, market_data_error_handler
from app.core.log_config import setup_logging

setup_logging()

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
            client = (
                f"{request.client.host}:{request.client.port}"
                if request.client else "-"
            )
            ua = request.headers.get("user-agent", "-")
            ver = request.scope.get("http_version", "1.1")
            _access_log.info(
                '%s - "%s %s HTTP/%s" %d %.0fms "%s"',
                client, request.method, request.url.path,
                ver, status_code, ms, ua,
            )


_settings = get_settings()
_meter_provider = None
_tracer_provider = None
if _settings.otel_enabled:
    from app.core.telemetry import setup_telemetry
    _meter_provider, _tracer_provider = setup_telemetry(
        _settings.otel_service_name,
        _settings.otel_exporter_otlp_endpoint,
        _settings.otel_export_interval_ms,
        _settings.otel_exporter_otlp_headers,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # uvicorn calls logging.config.dictConfig during startup, resetting logger
    # levels - silence uvicorn.access here, after dictConfig has run.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    yield
    if _meter_provider is not None:
        _meter_provider.shutdown()
        _tracer_provider.shutdown()


app = FastAPI(title="PestoENGINE API", version="2.0.0", lifespan=lifespan)

if _tracer_provider is not None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(
        app,
        meter_provider=_meter_provider,
        tracer_provider=_tracer_provider,
    )

app.add_middleware(_AccessLogMiddleware)

_cors = get_settings().cors_origins
_origins = [o.strip() for o in _cors.split(",") if o.strip()] if _cors else []
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_exception_handler(MarketDataError, market_data_error_handler)
app.include_router(health.router, prefix="/v1")
app.include_router(rebalance.router, prefix="/v1")
app.include_router(tickers.router, prefix="/v1")


def _mount_ui(application: FastAPI, ui_dist: Path) -> None:
    if ui_dist.exists():
        application.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")


_mount_ui(app, Path(__file__).resolve().parent.parent / "ui" / "dist")
