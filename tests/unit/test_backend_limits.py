"""Boundary validation, bounded storage and Redis failure behavior."""

from copy import deepcopy
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from redis import ConnectionError as RedisConnectionError

from app.core.config import Settings
from app.core.exceptions import CacheUnavailableError
from app.core.redis_client import create_redis_client
from app.market_data.cache import LocalCache
from app.market_data.redis_cache import RedisCache
from app.rate_limit.local_store import LocalRateLimitStore
from app.schemas.request import RebalanceRequest

PAYLOAD = {
    "only_buy": True,
    "increment": 10,
    "base_currency": "EUR",
    "assets": [
        {"ticker": "A", "desired_percentage": 50, "shares": 0, "fees": 0},
        {"ticker": "B", "desired_percentage": 50, "shares": 0, "fees": 0},
    ],
}


@pytest.mark.parametrize(
    "field,value",
    [
        ("shares", "1e30"),
        ("fees", "1e30"),
        ("shares", "0.1234567"),
        ("desired_percentage", "50.0000001"),
        ("provider", "yahho"),
        ("ticker", " " * 10),
        ("ticker", "A" * 65),
        ("ticker", "A B"),
    ],
)
def test_invalid_asset_inputs_are_rejected_before_provider_work(
    client, mock_registry, field, value
):
    payload = deepcopy(PAYLOAD)
    payload["assets"][0][field] = value
    assert client.post("/v1/rebalance", json=payload).status_code == 422
    mock_registry.get_quotes_for_assets.assert_not_called()


def test_exact_weight_sum_and_asset_count_are_enforced(client, mock_registry):
    payload = deepcopy(PAYLOAD)
    payload["assets"][0]["desired_percentage"] = "50.004"
    assert client.post("/v1/rebalance", json=payload).status_code == 422
    payload["assets"] *= 51
    assert client.post("/v1/rebalance", json=payload).status_code == 422
    payload = deepcopy(PAYLOAD)
    payload["increment"] = "1e30"
    assert client.post("/v1/rebalance", json=payload).status_code == 422
    mock_registry.get_quotes_for_assets.assert_not_called()


def test_normalization_keeps_valid_precision():
    payload = deepcopy(PAYLOAD)
    payload["assets"][0].update(ticker=" aapl ", provider=" Yahoo ", shares="0.123456")
    result = RebalanceRequest.model_validate(payload)
    assert result.assets[0].ticker == "AAPL"
    assert result.assets[0].provider == "yahoo"
    assert result.assets[0].shares == Decimal("0.123456")


@pytest.mark.parametrize("query", ["  ", "A" * 65, "AB\x00"])
def test_invalid_search_queries_fail_validation(client, query):
    assert client.get("/v1/tickers/search", params={"q": query}).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("cache_ttl_seconds", 0),
        ("fx_cache_ttl_seconds", -1),
        ("local_cache_max_entries", 0),
        ("otel_export_interval_ms", 0),
        ("quote_max_age_days", -1),
        ("redis_timeout_seconds", 0),
        ("provider_timeout_seconds", 0),
        ("provider_request_budget_seconds", 0),
        ("provider_concurrency", 33),
        ("otel_exporter_otlp_endpoint", "ftp://example.test"),
        ("otel_service_name", "  "),
        ("redis_url", "https://example.test"),
        ("redis_url", "redis://"),
    ],
)
def test_invalid_runtime_settings_fail_at_startup(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_empty_credentials_do_not_satisfy_required_configuration():
    with pytest.raises(ValidationError, match="REDIS_URL"):
        Settings(_env_file=None, cache_backend="redis", redis_url="   ")
    with pytest.raises(ValidationError, match="ALPHA_VANTAGE_API_KEY"):
        Settings(_env_file=None, market_data_providers=["alphavantage"], alpha_vantage_api_key="  ")


def test_local_cache_reclaims_never_reused_keys_and_bounds_capacity():
    clock = MagicMock(return_value=0)
    cache = LocalCache(60, clock, max_entries=10)
    for i in range(1000):
        cache.set(str(i), i)
    assert len(cache._store) == 10
    assert cache.get("0") is None
    assert cache.get("999") == 999
    clock.return_value = 60
    assert cache.get("999") is None
    assert not cache._store


def test_local_limiter_reclaims_epoch_minute_keys_without_resetting_active_ttl():
    clock = MagicMock(return_value=0)
    store = LocalRateLimitStore(clock, max_entries=10)
    for i in range(1000):
        store.increment(f"old:{i}", 60)
    assert len(store._data) == 10
    clock.return_value = 59
    assert store.increment("old:999", 60) == 2
    clock.return_value = 60
    assert store.increment("new:1", 60) == 1
    assert list(store._data) == ["new:1"]


@pytest.mark.parametrize("operation", ["get", "set"])
def test_redis_cache_failures_are_domain_errors(operation):
    client = MagicMock()
    client.get.side_effect = RedisConnectionError("offline")
    client.setex.side_effect = RedisConnectionError("offline")
    cache = RedisCache("redis://localhost", 60, encode=str, decode=str, client=client)
    with pytest.raises(CacheUnavailableError):
        cache.get("key") if operation == "get" else cache.set("key", "value")


def test_redis_client_has_explicit_timeouts_and_no_retries():
    client = create_redis_client("redis://localhost", 1.5)
    try:
        options = client.connection_pool.connection_kwargs
        assert options["socket_timeout"] == options["socket_connect_timeout"] == 1.5
        assert options["retry"].get_retries() == 0
    finally:
        client.close()
