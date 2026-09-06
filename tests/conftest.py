"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_fx_provider, get_registry
from app.core.config import Settings, get_settings
from app.fx.ecb_provider import EcbFxProvider
from app.market_data.provider_registry import ProviderRegistry


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
    from app.main import app
    app.dependency_overrides[get_registry] = lambda: mock_registry
    app.dependency_overrides[get_fx_provider] = lambda: mock_fx_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def pytest_configure() -> None:
    # Tests must not load credentials or infrastructure from a developer's .env.
    Settings.model_config["env_file"] = None
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_unmocked_provider_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Test attempted unmocked outbound HTTP")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
