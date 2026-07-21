"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.api.deps import get_fx_provider, get_registry, get_rate_limit_store
from app.fx.ecb_provider import EcbFxProvider
from app.market_data.provider_registry import ProviderRegistry
from app.rate_limit.local_store import LocalRateLimitStore


@pytest.fixture
def mock_registry() -> MagicMock:
    return MagicMock(spec=ProviderRegistry)


@pytest.fixture
def mock_fx_provider() -> MagicMock:
    return MagicMock(spec=EcbFxProvider)


@pytest.fixture
def client(
    mock_registry: MagicMock,
    mock_fx_provider: MagicMock,
) -> TestClient:
    app.dependency_overrides[get_registry] = lambda: mock_registry
    app.dependency_overrides[get_fx_provider] = lambda: mock_fx_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limit_store():
    yield
    store = get_rate_limit_store()
    if isinstance(store, LocalRateLimitStore):
        with store._lock:
            store._data.clear()
