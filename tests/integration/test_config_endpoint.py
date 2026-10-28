"""Integration tests for the frontend runtime-configuration contract."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_runtime_config_exposes_backend_currency_policy(client):
    response = client.get("/v1/config")

    assert response.status_code == 200
    assert response.json() == {
        "base_currencies": ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD"],
        "rebalance_engine": "backend",
    }


def test_runtime_config_exposes_browser_engine_switch():
    app = create_app(Settings(_env_file=None, rebalance_engine="frontend"))
    with TestClient(app) as client:
        assert client.get("/v1/config").json()["rebalance_engine"] == "frontend"
