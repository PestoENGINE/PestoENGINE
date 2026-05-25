"""Integration tests for RateLimitMiddleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics import MeterProvider

from app.rate_limit.local_store import LocalRateLimitStore
from app.rate_limit.middleware import RateLimitMiddleware

_NOOP_MP = MeterProvider()

_REBALANCE_PAYLOAD = {
    "only_buy": True,
    "increment": 100.0,
    "assets": [{"ticker": "A", "desired_percentage": 100.0, "shares": 0, "fees": 0}],
}


@pytest.fixture
def store():
    return LocalRateLimitStore()


@pytest.fixture
def rate_limited_client(store):
    test_app = FastAPI()
    # RateLimit added first (inner, runs second); no ProxyHeaders here
    test_app.add_middleware(
        RateLimitMiddleware, store=store, limit=2, meter_provider=_NOOP_MP
    )

    @test_app.post("/v1/rebalance")
    def fake_rebalance():
        return {"ok": True}

    @test_app.get("/v1/tickers/search")
    def fake_search():
        return {"ok": True}

    @test_app.get("/v1/health")
    def fake_health():
        return {"ok": True}

    with TestClient(test_app) as c:
        yield c


def test_requests_under_limit_return_200(rate_limited_client):
    r1 = rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    r2 = rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_request_over_limit_returns_429(rate_limited_client):
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    r = rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    assert r.status_code == 429


def test_429_has_retry_after_header(rate_limited_client):
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    r = rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    assert "retry-after" in r.headers
    assert 1 <= int(r.headers["retry-after"]) <= 60


def test_health_endpoint_not_rate_limited(rate_limited_client):
    for _ in range(5):
        r = rate_limited_client.get("/v1/health")
        assert r.status_code == 200


def test_search_endpoint_shares_bucket_with_rebalance(rate_limited_client):
    # rebalance + search share the same bucket per IP
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    rate_limited_client.get("/v1/tickers/search")
    r = rate_limited_client.get("/v1/tickers/search")
    assert r.status_code == 429


def test_429_response_body_has_detail(rate_limited_client):
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    r = rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    assert r.status_code == 429
    body = r.json()
    assert "detail" in body
    assert "Rate limit exceeded" in body["detail"]


def test_options_request_not_rate_limited(rate_limited_client):
    for _ in range(2):
        rate_limited_client.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
    r = rate_limited_client.options("/v1/rebalance")
    assert r.status_code != 429


def test_store_error_fails_open():
    from unittest.mock import MagicMock
    broken_store = MagicMock()
    broken_store.increment.side_effect = RuntimeError("store unavailable")

    test_app = FastAPI()
    test_app.add_middleware(
        RateLimitMiddleware, store=broken_store, limit=2, meter_provider=_NOOP_MP
    )

    @test_app.post("/v1/rebalance")
    def fake_rebalance():
        return {"ok": True}

    with TestClient(test_app) as c:
        r = c.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
        assert r.status_code == 200


def test_no_middleware_never_returns_429():
    test_app = FastAPI()

    @test_app.post("/v1/rebalance")
    def fake_rebalance():
        return {"ok": True}

    with TestClient(test_app) as c:
        for _ in range(10):
            r = c.post("/v1/rebalance", json=_REBALANCE_PAYLOAD)
            assert r.status_code == 200


def test_xff_ip_used_when_proxy_trusted(store):
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    test_app = FastAPI()
    # LIFO: RateLimit added first (inner/second), ProxyHeaders added last (outer/first)
    test_app.add_middleware(
        RateLimitMiddleware, store=store, limit=2, meter_provider=_NOOP_MP
    )
    test_app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

    @test_app.post("/v1/rebalance")
    def fake_rebalance():
        return {"ok": True}

    with TestClient(test_app, raise_server_exceptions=True) as c:
        # Two requests from "1.2.3.4" via XFF — within limit
        for _ in range(2):
            r = c.post(
                "/v1/rebalance",
                json=_REBALANCE_PAYLOAD,
                headers={"X-Forwarded-For": "1.2.3.4"},
            )
            assert r.status_code == 200

        # Third request from same XFF IP — over limit
        r = c.post(
            "/v1/rebalance",
            json=_REBALANCE_PAYLOAD,
            headers={"X-Forwarded-For": "1.2.3.4"},
        )
        assert r.status_code == 429

        # Different XFF IP — separate bucket, should pass
        r = c.post(
            "/v1/rebalance",
            json=_REBALANCE_PAYLOAD,
            headers={"X-Forwarded-For": "5.6.7.8"},
        )
        assert r.status_code == 200
