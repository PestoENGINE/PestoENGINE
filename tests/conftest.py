"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.api.deps import get_market_provider
from app.market_data.base import AbstractMarketDataProvider


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock(spec=AbstractMarketDataProvider)
    return provider


@pytest.fixture
def client(mock_provider: MagicMock) -> TestClient:
    app.dependency_overrides[get_market_provider] = lambda: mock_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
