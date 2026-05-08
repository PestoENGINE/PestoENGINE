"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.api.deps import get_registry
from app.market_data.provider_registry import ProviderRegistry


@pytest.fixture
def mock_registry() -> MagicMock:
    return MagicMock(spec=ProviderRegistry)


@pytest.fixture
def client(mock_registry: MagicMock) -> TestClient:
    app.dependency_overrides[get_registry] = lambda: mock_registry
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
