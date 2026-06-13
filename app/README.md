# PestoENGINE – Backend

FastAPI service exposing the rebalance algorithm and ticker search via HTTP. Pydantic v2 schemas at the HTTP boundary, pure-function algorithms in `app/rebalance/`. OpenTelemetry instrumented (metrics, traces, logs).

Python 3.11+ required (3.12 in the production Docker image).

## Stack

| Layer | Library | Notes |
|-------|---------|-------|
| Web framework | FastAPI ≥0.111 | async routes; sync `run_rebalance` offloaded to thread executor |
| Validation | Pydantic v2 + pydantic-settings | `.env` loaded into a typed `Settings` |
| HTTP client | httpx ≥0.28 | sync; market data fetch is blocking I/O |
| Cache (optional) | redis ≥5 | lazy import; only loaded when `CACHE_BACKEND=redis` |
| Observability | OpenTelemetry SDK ≥1.25 | metrics + traces + logs via OTLP/HTTP |
| ASGI server | uvicorn[standard] ≥0.29 | |
| Tests | pytest ≥9.0 | `testpaths=tests`, `pythonpath=app` (see `pytest.ini`) |

## Structure

```
app/
├── main.py         # FastAPI app, middleware, OTel init, static UI mount
├── api/            # Routes (rebalance, tickers, health) + DI (deps.py)
├── schemas/        # Pydantic v2 request/response models
├── services/       # rebalance_service: orchestration + two-pass fee math
├── rebalance/      # Pure algorithms (greedy + knapsack DP)
├── market_data/    # Provider abstractions, Yahoo/AV adapters, cache, decorators
└── core/           # Config, exceptions, formatting, JSON logging, OTel telemetry
```

## Provider stack (decorator chain)

Each configured market data provider is wrapped at startup (`api/deps.py:_build_registry`):

```
ProviderRegistry
  └── CachedMarketDataProvider                # cache hit/miss + cache_ops counter
        └── InstrumentedMarketDataProvider    # fetch_duration histogram + fetch_total counter + span
              └── YahooFinanceProvider | AlphaVantageProvider   # raw HTTP via httpx
```

Only cache misses reach the instrumented layer, so `pestoengine_market_fetch_duration_seconds` measures real API latency and not cache hits. Cache keys use the prefix `market:price:{provider_id}:{ticker}`.

`ProviderRegistry` routes assets in two modes:

- Assets with an explicit `provider` field are batched per provider and fail fast (the whole batch raises if the provider raises).
- Assets with `provider: null` go through the per-ticker fallback chain (in `MARKET_DATA_PROVIDERS` order); the first provider that returns a price wins.

## Request flow: `POST /v1/rebalance`

```
HTTP request
  → FastAPI route (async)
  → loop.run_in_executor(None, run_rebalance, payload, registry)
  → run_rebalance()                                      [span: rebalance_compute]
      → registry.get_prices_for_assets(assets)
          → CachedMarketDataProvider.get_prices()        [span: cache_lookup]
              hit  → return cached price
              miss → InstrumentedMarketDataProvider.get_prices()    [span: market_fetch]
                       → raw provider (httpx)
                       → set cache
      → calculate_rebalance()                            (pure math; only_buy switches gap redistribution vs. full rebalance)
      → _apply_fee() per asset → buy_quantities (floor div by ticker_price, or exact 6-dp fraction when fractional_shares=true)
      → redistribute_change() | redistribute_change_optimal()    (knapsack DP when optimal_redistribute=true; skipped when fractional_shares=true)
      → second pass: recompute percentage fees + change on final quantities
      → RebalanceResponse
```

## HTTP API

### `POST /v1/rebalance`

Request:

```json
{
  "only_buy": true,
  "increment": 1000,
  "optimal_redistribute": false,
  "fractional_shares": false,
  "assets": [
    {"ticker": "VWCE.DE", "provider": null, "desired_percentage": 60, "shares": 10, "fees": 0.5, "percentage_fee": true},
    {"ticker": "VAGF.DE", "provider": null, "desired_percentage": 40, "shares": 5,  "fees": 1.5, "percentage_fee": false}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `only_buy` | bool | When `true`, never sell; distribute the increment among underweight assets only |
| `increment` | float ≥0 | Cash to deploy this period |
| `optimal_redistribute` | bool (default `false`) | Use knapsack DP for the leftover-change step |
| `fractional_shares` | bool (default `false`) | Buy exact fractional quantities (6 dp) instead of whole shares; each asset lands on its target and the leftover-change step is skipped |
| `assets[].ticker` | string (non-empty) | Symbol recognized by the chosen provider |
| `assets[].provider` | string \| null | `"yahoo"` / `"alphavantage"` for direct routing; `null` to use the fallback chain |
| `assets[].desired_percentage` | float 0..100 | All assets must sum to exactly `100` |
| `assets[].shares` | float ≥0 | Shares currently held |
| `assets[].percentage_fee` | bool (default `false`) | `false`: flat fee; `true`: % of transaction value |
| `assets[].fees` | float ≥0 | Absolute amount when `percentage_fee=false`; `0..100` when `true` |

Response (`200 OK`):

```json
{
  "results": [
    {"id": 0, "ticker": "VWCE.DE", "current_percentage": 37.45, "desired_percentage": 60.0,
     "shares": 10, "allocated": 594.05, "ticker_price": 118.42, "fees": 2.97, "buy": 5.0},
    {"id": 1, "ticker": "VAGF.DE", "current_percentage": 62.55, "desired_percentage": 40.0,
     "shares": 5, "allocated": 398.5, "ticker_price": 23.18, "fees": 1.5, "buy": 17.0}
  ],
  "total_fees": 4.47,
  "change": 6.52
}
```

`buy` is a float: an integer-valued share count in whole-share mode (`5.0`), or a
fractional quantity truncated to 6 decimals when `fractional_shares=true`.

Errors:

- `422`: schema validation failed (e.g. `desired_percentage` does not sum to 100, percentage fee > 100)
- `502`: market data fetch failed; body is `{"detail": "..."}` (raised as `MarketDataError`)

### `GET /v1/tickers/search`

Query parameters: `q` (string, min length 2). Calls all configured search providers in parallel via `asyncio.gather` and merges results.

```json
{
  "results": [
    {"ticker": "VWCE.DE", "name": "YF · Vanguard FTSE All-World UCITS ETF",
     "exchange": "XETRA", "type": "ETF", "provider": "yahoo"}
  ]
}
```

`type` is one of: `EQUITY`, `ETF`, `MUTUALFUND`, `CRYPTOCURRENCY`, `CURRENCY`. Indices, futures, and options are filtered out. `name` is prefixed with a provider label (`YF · ...`, `AV · ...`). `exchange` is a human-readable market label (Yahoo's exchange display name such as `XETRA`/`Milan`/`NASDAQ`, falling back to its code; Alpha Vantage's region). `provider` round-trips to `POST /v1/rebalance`.

Errors:

- `422`: `q` absent or shorter than 2 characters
- `503`: all configured search providers failed

### `GET /v1/health`, `GET /v1/ready`

- `/v1/health`: always `200` (liveness probe)
- `/v1/ready`: `200` unless `CACHE_BACKEND=redis` and `redis.ping()` fails (then `503`)

## Configuration

Read from `.env` (see [`.env.example`](../.env.example)):

| Variable | Default | Purpose |
|----------|---------|---------|
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `CACHE_BACKEND` | `local` | `local`: per-process dict; `redis`: shared across workers |
| `CACHE_TTL_SECONDS` | `300` | Price cache TTL |
| `REDIS_URL` | unset | Required when `CACHE_BACKEND=redis` |
| `CORS_ORIGINS` | unset | Comma-separated list; only needed when the frontend is on a different origin |
| `MARKET_DATA_PROVIDERS` | `["yahoo"]` | JSON list of provider IDs, in fallback order |
| `ALPHA_VANTAGE_API_KEY` | unset | Required when `alphavantage` is configured |
| `RATE_LIMIT_PROVIDERS_PER_MIN` | unset | Requests per IP per minute on `/v1/rebalance` and `/v1/tickers/search`; unset = disabled. With multiple uvicorn workers (`--workers N`) the limit is per-worker; use `CACHE_BACKEND=redis` for a shared counter |
| `TRUSTED_PROXIES` | unset | Comma-separated IPs trusted for `X-Forwarded-For`; `*` for Render/any upstream; unset = always use TCP source IP |
| `FASTAPI_DOCS` | `true` | Set `false` in production to hide `/docs`, `/redoc`, and `/openapi.json` |
| `OTEL_ENABLED` | `false` | Enables OTLP/HTTP export of metrics + traces + logs |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Base URL; `/v1/metrics`, `/v1/traces`, `/v1/logs` are appended |
| `OTEL_SERVICE_NAME` | `pestoengine` | OTel resource attribute |
| `OTEL_EXPORT_INTERVAL_MS` | `60000` | Periodic metric export interval |
| `OTEL_EXPORTER_OTLP_HEADERS` | unset | Comma-separated `k=v` (URL-encoded values), e.g. Grafana Cloud auth |

## Observability

When `OTEL_ENABLED=true`, `app.core.telemetry.setup_telemetry` configures OTLP/HTTP exporters. The FastAPI app is auto-instrumented by `opentelemetry-instrumentation-fastapi` (HTTP request spans).

### Metrics

| Name | Type | Unit | Labels |
|------|------|------|--------|
| `pestoengine_market_fetch_duration_seconds` | histogram | s | `provider` |
| `pestoengine_market_fetch_total` | counter | tickers | `provider`, `outcome` (`success` / `error`) |
| `pestoengine_cache_ops_total` | counter | ops | `backend` (`local` / `redis`), `result` (`hit` / `miss`) |
| `pestoengine_provider_errors_total` | counter | errors | `provider`, `error_type` (`explicit` / `fallback`) |
| `pestoengine_rebalance_duration_seconds` | histogram | s | `algorithm` (`greedy` / `dp`) |
| `pestoengine_rebalance_tickers` | histogram | tickers | (none) |
| `pestoengine_rate_limit_total` | counter | requests | `outcome` (`allowed` / `denied`), `endpoint` (`rebalance` / `search`) |

`pestoengine_market_fetch_duration_seconds` uses explicit bucket boundaries `[0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0]` (set via a `View` in `telemetry.py`) for sub-100ms resolution.

### Spans

| Span | Source | Attributes |
|------|--------|------------|
| `rebalance_compute` | `services/rebalance_service.py` | `rebalance.algorithm`, `rebalance.tickers.count`, `rebalance.only_buy`, `rebalance.increment` |
| `cache_lookup` | `market_data/cached_provider.py` | `cache.backend`, `provider`, `tickers.count`, `cache.hits`, `cache.misses` |
| `market_fetch` | `market_data/instrumented_provider.py` | `provider`, `tickers.count` |

### Logs

JSON formatter (`core/log_config.py`) emits one JSON object per line with `ts`, `level`, `logger`, `msg`. When an OTel span is active, `trace_id` and `span_id` are injected automatically. When `OTEL_ENABLED=true`, log records are also exported via OTLP/HTTP to the configured endpoint (Loki-compatible via Grafana Alloy).

The `_AccessLogMiddleware` (in `main.py`) emits one structured access log for every request that reaches the router, with `http_method`, `http_path`, `http_status`, `http_duration_ms`, `http_client`, `http_user_agent`, `http_version`. Requests short-circuited further out in the middleware stack (429s from the rate limiter, CORS preflights) are not access-logged; rate-limit decisions are counted by `pestoengine_rate_limit_total`.

## Setup

```bash
python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

Service listens on `http://localhost:8000`. OpenAPI docs at `/docs`, ReDoc at `/redoc`.

## Test

```bash
pytest                    # all tests
pytest tests/unit         # unit only
pytest tests/integration  # integration only
pytest -q --tb=short      # CI style
```

Fixtures in `tests/conftest.py`:

- `mock_registry`: `MagicMock(spec=ProviderRegistry)`
- `client`: `TestClient(app)` with `get_registry` overridden to return `mock_registry`

No real HTTP calls are made in tests.

## Calling the API

### curl

```bash
curl -X POST http://localhost:8000/v1/rebalance \
     -H "Content-Type: application/json" \
     -d @../portfolios/portfolio.json | jq
```

### Python (`httpx`)

```python
import httpx

payload = {
    "only_buy": True,
    "increment": 1000,
    "optimal_redistribute": False,
    "assets": [
        {"ticker": "VWCE.DE", "provider": None, "desired_percentage": 60, "shares": 10, "fees": 0.5, "percentage_fee": True},
        {"ticker": "VAGF.DE", "provider": None, "desired_percentage": 40, "shares": 5,  "fees": 1.5, "percentage_fee": False},
    ],
}

response = httpx.post("http://localhost:8000/v1/rebalance", json=payload)
response.raise_for_status()
print(response.json())
```
