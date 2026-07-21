"""Integration tests for the frontend runtime-configuration contract."""


def test_runtime_config_exposes_backend_currency_policy(client):
    response = client.get("/v1/config")

    assert response.status_code == 200
    assert response.json() == {
        "base_currencies": ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD"],
    }
