"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import health, rebalance, tickers
from app.core.config import get_settings
from app.core.exceptions import MarketDataError, market_data_error_handler
from app.core.log_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(title="PestoENGINE API", version="2.0.0", lifespan=lifespan)

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
