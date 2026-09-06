"""Exercise actual middleware order, lifespan, worker bounds and trace continuity."""

import asyncio
import threading
from contextvars import ContextVar
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from redis import ConnectionError as RedisConnectionError

from app.api.resources import AppResources
from app.api.work import run_provider_work
from app.core.config import Settings
from app.main import create_app
from app.market_data.alpha_vantage_search_provider import AlphaVantageSearchProvider
from tests.helpers import make_quote

PAYLOAD = {
    "only_buy": True,
    "increment": 10,
    "base_currency": "EUR",
    "assets": [
        {"ticker": "A", "desired_percentage": 100, "shares": 0, "fees": 0},
    ],
}


def settings(**kwargs):
    return Settings(_env_file=None, **kwargs)


def test_lifespan_owns_reuses_and_closes_clients():
    app = create_app(settings())
    assert app.state.resources is None
    with TestClient(app) as client:
        first = app.state.resources
        assert first.registry._providers["yahoo"]._provider._provider._client is first.client
        assert first.fx_provider._client is first.client
        assert first.search_providers[0]._client is first.client
        assert client.get("/v1/ready").status_code == 200
    assert first.client.is_closed
    assert app.state.resources is None
    with TestClient(app):
        assert app.state.resources is not first
        assert not app.state.resources.client.is_closed


def test_initialization_failure_closes_already_created_resources(monkeypatch):
    client = httpx.Client()
    monkeypatch.setattr("app.api.resources.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "app.api.resources.YahooFinanceProvider", MagicMock(side_effect=RuntimeError("init failed"))
    )
    with pytest.raises(RuntimeError, match="init failed"):
        AppResources(settings())
    assert client.is_closed


def test_rate_limit_response_has_cors_retry_and_security_headers():
    app = create_app(settings(rate_limit_providers_per_min=1, cors_origins="https://ui.test"))
    with TestClient(app) as client:
        app.state.resources.search_providers = [MagicMock(search=MagicMock(return_value=[]))]
        headers = {"Origin": "https://ui.test"}
        assert client.get("/v1/tickers/search?q=IBM", headers=headers).status_code == 200
        response = client.get("/v1/tickers/search?q=IBM", headers=headers)
        assert response.status_code == 429
        assert response.headers["Access-Control-Allow-Origin"] == "https://ui.test"
        assert "Retry-After" in response.headers["Access-Control-Expose-Headers"]
        assert int(response.headers["Retry-After"]) > 0
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert client.get("/v1/health").status_code == 200


def test_blocking_rate_store_does_not_block_health():
    started, release = threading.Event(), threading.Event()

    class BlockingStore:
        def increment(self, *args, **kwargs):
            started.set()
            assert release.wait(2)
            return 1

    async def scenario():
        app = create_app(settings(rate_limit_providers_per_min=10))
        async with app.router.lifespan_context(app):
            app.state.resources.rate_limit_store = BlockingStore()
            app.state.resources.search_providers = [MagicMock(search=MagicMock(return_value=[]))]
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                request = asyncio.create_task(client.get("/v1/tickers/search?q=IBM"))
                try:
                    assert await asyncio.to_thread(started.wait, 1)
                    response = await asyncio.wait_for(client.get("/v1/health"), 0.5)
                    assert response.status_code == 200
                    assert not request.done()
                finally:
                    release.set()
                    await request

    asyncio.run(scenario())


def test_redis_outage_uses_same_client_for_cache_and_readiness(monkeypatch):
    redis = MagicMock()
    redis.get.side_effect = RedisConnectionError("test outage")
    redis.ping.side_effect = RedisConnectionError("test outage")
    monkeypatch.setattr("app.api.resources.create_redis_client", lambda *args: redis)
    app = create_app(settings(cache_backend="redis", redis_url="redis://localhost:6379"))
    with TestClient(app) as client:
        response = client.post("/v1/rebalance", json=PAYLOAD)
        assert response.status_code == 503
        assert response.json() == {"detail": "Cache unavailable"}
        assert client.get("/v1/ready").status_code == 503
        assert client.get("/v1/health").status_code == 200
        assert app.state.resources.redis_client is redis
    redis.close.assert_called_once()


def test_alpha_quota_returns_503_but_genuine_empty_search_succeeds():
    app = create_app(settings())
    body = {"Note": "quota exhausted"}
    with (
        TestClient(app) as client,
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ) as upstream,
    ):
        app.state.resources.search_providers = [
            AlphaVantageSearchProvider("test-key", client=upstream)
        ]
        assert client.get("/v1/tickers/search?q=IBM").status_code == 503
        body = {"bestMatches": []}
        response = client.get("/v1/tickers/search?q=IBM")
        assert response.status_code == 200
        assert response.json() == {"results": []}


def test_request_validation_uses_each_apps_settings():
    eur = create_app(settings(base_currency=["EUR"]))
    usd = create_app(settings(base_currency=["USD"]))
    with TestClient(eur) as eur_client, TestClient(usd) as usd_client:
        eur.state.resources.registry = MagicMock(
            get_quotes_for_assets=MagicMock(return_value=[make_quote(10)])
        )
        assert eur_client.post("/v1/rebalance", json=PAYLOAD).status_code == 200
        assert usd_client.post("/v1/rebalance", json=PAYLOAD).status_code == 422
        assert usd_client.get("/v1/config").json() == {"base_currencies": ["USD"]}


def test_rebalance_compute_keeps_http_parent_span_and_restarts_sdk(monkeypatch):
    exporters = []

    def telemetry(*args, **kwargs):
        exporter = InMemorySpanExporter()
        exporters.append(exporter)
        tracer = TracerProvider()
        tracer.add_span_processor(SimpleSpanProcessor(exporter))
        return MeterProvider(), tracer, LoggerProvider()

    monkeypatch.setattr("app.api.resources.setup_telemetry", telemetry)
    app = create_app(settings(otel_enabled=True))
    for _ in range(2):
        with TestClient(app) as client:
            app.state.resources.registry = MagicMock(
                get_quotes_for_assets=MagicMock(return_value=[make_quote(10)])
            )
            assert client.post("/v1/rebalance", json=PAYLOAD).status_code == 200
            spans = exporters[-1].get_finished_spans()
            computation = next(s for s in spans if s.name == "rebalance_compute")
            parent = next(s for s in spans if s.context.span_id == computation.parent.span_id)
            assert parent.context.trace_id == computation.context.trace_id
            assert parent.kind.name == "SERVER"
    assert len(exporters) == 2


@pytest.mark.parametrize("cancel", [False, True])
def test_worker_timeout_and_cancellation_keep_slot_until_thread_finishes(cancel):
    started, release = threading.Event(), threading.Event()
    marker = ContextVar("test_marker", default="missing")

    def blocking():
        started.set()
        assert release.wait(2)
        assert marker.get() == "request-context"
        return 42

    async def scenario():
        resources = AppResources(
            settings(provider_concurrency=1, provider_request_budget_seconds=0.05)
        )
        marker.set("request-context")
        task = asyncio.create_task(run_provider_work(resources, blocking))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            if cancel:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                with pytest.raises(HTTPException) as error:
                    await task
                assert error.value.status_code == 503
            assert resources.semaphore.locked()
            second = MagicMock()
            with pytest.raises(HTTPException):
                await run_provider_work(resources, second)
            second.assert_not_called()
        finally:
            release.set()
            await asyncio.gather(*resources.pending_work, return_exceptions=True)
            resources.close()
        assert not resources.semaphore.locked()

    asyncio.run(scenario())


def test_cooperative_provider_deadline_is_503_and_does_not_try_fallback():
    from app.core.exceptions import ProviderDeadlineError
    from app.market_data.provider_registry import ProviderRegistry

    app = create_app(settings())
    first, fallback = MagicMock(), MagicMock()
    first.get_quotes.side_effect = ProviderDeadlineError("deadline exceeded")
    with TestClient(app) as client:
        app.state.resources.registry = ProviderRegistry(
            {"yahoo": first, "alphavantage": fallback},
            ["yahoo", "alphavantage"],
        )
        assert client.post("/v1/rebalance", json=PAYLOAD).status_code == 503
    fallback.get_quotes.assert_not_called()
