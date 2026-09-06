"""FastAPI dependencies resolve resources belonging to the current application."""

from fastapi import Request

from app.api.resources import AppResources
from app.core.config import Settings
from app.fx.ecb_provider import EcbFxProvider
from app.market_data.base import AbstractTickerSearchProvider
from app.market_data.provider_registry import ProviderRegistry
from app.rate_limit.base import AbstractRateLimitStore


def get_resources(request: Request) -> AppResources:
    return request.app.state.resources


def get_app_settings(request: Request) -> Settings:
    return get_resources(request).settings


def get_registry(request: Request) -> ProviderRegistry:
    return get_resources(request).registry


def get_fx_provider(request: Request) -> EcbFxProvider:
    return get_resources(request).fx_provider


def get_search_providers(request: Request) -> list[AbstractTickerSearchProvider]:
    return get_resources(request).search_providers


def get_rate_limit_store(request: Request) -> AbstractRateLimitStore | None:
    return get_resources(request).rate_limit_store
