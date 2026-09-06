# PestoENGINE – Backend

FastAPI service exposing the rebalance algorithm and ticker search via HTTP. Pydantic v2 schemas at the HTTP boundary, pure-function algorithms in `app/rebalance/`. OpenTelemetry instrumented (metrics, traces, logs).

Python 3.11+ required (3.12 in the production Docker image).

## Stack

| Layer | Library | Notes |
|-------|---------|-------|
| Web framework | FastAPI ≥0.111 | async routes; sync `run_rebalance` offloaded to thread executor |
| Validation | Pydantic v2 + pydantic-settings | `.env` loaded into a typed `Settings` |
| HTTP client | httpx ≥0.28 | sync; market data fetch is blocking I/O |
| Cache (optional) | redis ≥5 | one shared client when `CACHE_BACKEND=redis` |
| Observability | OpenTelemetry SDK ≥1.25 | metrics + traces + logs via OTLP/HTTP |
| ASGI server | uvicorn[standard] ≥0.29 | |
| Tests | pytest ≥9.0 | `testpaths=tests` (see `pytest.ini`) |

## Structure

```
app/
├── main.py         # FastAPI app, middleware, OTel init, static UI mount
├── api/            # Routes (rebalance, tickers, health) + DI (deps.py)
├── schemas/        # Pydantic v2 request/response models
├── services/       # rebalance_service: orchestration + funded order planning
├── rebalance/      # Pure algorithms (greedy + knapsack DP)
├── market_data/    # Provider abstractions, Yahoo/AV adapters, cache, decorators
├── fx/             # ECB open-data adapter, Decimal triangulation, FX cache
└── core/           # Config, exceptions, formatting, JSON logging, OTel telemetry
```

## Provider stack (decorator chain)

Each configured market data provider is wrapped at startup (`api/resources.py:AppResources`):

```
ProviderRegistry
  └── CachedMarketDataProvider                # cache hit/miss + cache_ops counter
        └── InstrumentedMarketDataProvider    # fetch_duration histogram + fetch_total counter + span
              └── YahooFinanceProvider | AlphaVantageProvider   # raw HTTP via httpx
```

Only cache misses reach the instrumented layer. Cache entries contain a decimal
price, currency and observation date. Versioned cache keys include provider, ticker and currency hint. Registry results follow input row order, so identical tickers cannot overwrite each other.

`ProviderRegistry` routes assets in two modes:

- Assets with an explicit `provider` field are batched per provider and currency hint and fail fast (the whole batch raises if the provider raises).
- Assets with `provider: null` go through the per-ticker fallback chain (in `MARKET_DATA_PROVIDERS` order); the first provider that returns a complete quote wins.

Yahoo supplies quote currency in its chart metadata. Alpha Vantage
`GLOBAL_QUOTE` does not supply a reliable currency, so Alpha Vantage assets must
carry `assets[].currency` (normally round-tripped from ticker search). The
backend never infers currency from a ticker. Yahoo chart timestamps and Alpha
Vantage's latest trading day supply `quote_as_of`. Missing, future or overly old
observations fail closed, including cached prices. Cache TTL is separate from
observation age; the default seven calendar days accommodates weekends and holidays.

## ECB FX stack

`EcbFxProvider` reads public daily EXR rates, triangulates through EUR and uses
the configured local or Redis cache. There is no private FX fallback. Missing
or stale observations fail closed. The mandatory portfolio currency must be in
`BASE_CURRENCY`. All references used in a conversion share one observation date.
A partial cache hit or mixed cached dates refreshes the entire required set;
inconsistent upstream dates fail closed. `fx_as_of` identifies that reference
date, or is null when only a fixed unit conversion (such as GBX to GBP) is needed.

## Resource lifecycle and limits

`create_app(settings)` constructs the application; its lifespan owns one shared
HTTP client, the optional Redis client and the telemetry SDKs. Dependencies use
that application's resources. Shutdown drains outstanding work and closes them.
Importing the application does not create clients or start telemetry exporters.

Provider work has a configurable total budget (including queue time) and a
per-application concurrency cap. Executor work copies request/trace context. A
request timeout or cancellation retains its slot until the actual thread exits.
HTTP I/O checks the deadline between operations and response chunks, limits
decoded bodies to 2 MiB, and retries transport errors and HTTP 5xx up to three
attempts. HTTP 4xx, quotas and malformed responses are not retried. Individual
blocking operations may finish after the HTTP deadline; concurrency stays bounded.

Local price/FX caches and rate counters reclaim expired keys on access and have
a capacity limit. The limiter evicts oldest buckets at capacity; it is a
deterrent, not an authentication boundary. Redis counters increment and set or
repair TTL atomically with Lua. Redis I/O runs outside the event loop with
explicit timeouts and no automatic retries. Limiter failure remains fail-open;
configured Redis price/FX cache failure returns 503, matching readiness.

## Request flow: `POST /v1/rebalance`

```
HTTP request
  → FastAPI route (async)
  → run_provider_work(resources, run_rebalance, ...)  # bounded, with copied context
  → run_rebalance()                                      [span: rebalance_compute]
      → registry.get_quotes_for_assets(assets)
          → CachedMarketDataProvider.get_quotes()        [span: cache_lookup]
              hit  → return cached MarketQuote
              miss → InstrumentedMarketDataProvider.get_quotes()    [span: market_fetch]
                       → raw provider (httpx)
                       → set cache
      → EcbFxProvider.get_rates(quote currencies, base currency)  # cached ECB EXR conversion
      → calculate_rebalance()                            (pure math; only_buy switches gap redistribution vs. full rebalance)
      -> plan_orders(): capped sales -> actual net proceeds -> affordable buys
          -> whole shares: greedy | DP with positive-gap eligibility
          -> fractional shares: quantities truncated toward zero to 6 decimals
          -> final fees and remaining cash
      → RebalanceResponse
```

## HTTP API

### `POST /v1/rebalance`

Request:

```json
{
  "only_buy": true,
  "increment": 1000,
  "base_currency": "EUR",
  "optimal_redistribute": false,
  "fractional_shares": false,
  "assets": [
    {"ticker": "VOO", "provider": "yahoo", "currency": "USD", "desired_percentage": 60, "shares": 10, "fees": 0.5, "percentage_fee": true},
    {"ticker": "VAGF.DE", "provider": "yahoo", "currency": "EUR", "desired_percentage": 40, "shares": 5, "fees": 1.5, "percentage_fee": false}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `only_buy` | bool | When `true`, never sell; distribute the increment among underweight assets only |
| `increment` | JSON number ≥0 | Cash to deploy this period; parsed as `Decimal` |
| `base_currency` | required string | Calculation currency; must be included in the backend's `BASE_CURRENCY` list. Differing quotes are converted with ECB reference rates when the required series exists |
| `optimal_redistribute` | bool (default `false`) | Use knapsack DP for the leftover-change step |
| `fractional_shares` | bool (default `false`) | Use fractional quantities truncated to 6 dp; skip whole-share redistribution. Fees, truncation and buy-only constraints can prevent exact targets |
| `assets[].ticker` | string (1..64 characters) | Trimmed and upper-cased; embedded whitespace/control characters are rejected |
| `assets[].provider` | string \| null | `"yahoo"` / `"alphavantage"` for direct routing; `null` to use the fallback chain |
| `assets[].currency` | ISO code \| null | Quote-currency metadata. Required for Alpha Vantage; never guessed from the ticker |
| `assets[].desired_percentage` | JSON number 0..100 | All assets must sum to exactly `100`; parsed as `Decimal` |
| `assets[].shares` | JSON number ≥0 | Shares currently held; parsed as `Decimal` |
| `assets[].percentage_fee` | bool (default `false`) | `false`: flat fee; `true`: % of transaction value |
| `assets[].fees` | float ≥0 | Absolute amount when `percentage_fee=false`; `0..100` when `true` |

Requests contain 1..100 assets. `increment`, `shares` and `fees` are limited to
0..10^12 with at most six decimal places; target percentages also accept at most
six decimal places and must sum exactly to 100. Unknown provider IDs return 422.
Provider prices must be finite and within 10^-18..10^12; ECB rates within
10^-12..10^12. Calculations retain Decimal precision across conversion and orders.

Illustrative response (`200 OK`) for two equally weighted EUR assets, ten shares
each at 6 EUR, a 20 EUR increment and no fees (example data):

```json
{
  "results": [
    {"id": 0, "ticker": "A", "current_percentage": 50, "desired_percentage": 50,
     "shares": 10, "allocated": 12, "ticker_price": 6, "fees": 0, "buy": 2,
     "quote_as_of": "2026-09-04"},
    {"id": 1, "ticker": "B", "current_percentage": 50, "desired_percentage": 50,
     "shares": 10, "allocated": 6, "ticker_price": 6, "fees": 0, "buy": 1,
     "quote_as_of": "2026-09-04"}
  ],
  "total_fees": 0,
  "change": 2,
  "base_currency": "EUR",
  "fx_as_of": null
}
```

`buy` is a JSON number: an integer-valued share count in whole-share mode (`5.0`), or a
fractional quantity truncated to 6 decimals when `fractional_shares=true`.

Calculations use `Decimal`. Monetary response fields are expressed in the
request's `base_currency`. `allocated`, `fees`, `total_fees`, `change` and
percentages truncate to two decimals for display. `shares` and `ticker_price`
are not truncated to two decimals; normal JSON number precision applies.
`buy` retains six decimals. The
internal cash identity holds before display truncation, so displayed line-item
sums can differ from displayed totals. Six-decimal quantity truncation does not
guarantee less than a cent of change at every price.

Sales never exceed holdings and are skipped if fees consume their proceeds.
Buy budgets use the increment plus actual sale proceeds minus sale fees. Flat
fees apply once per nonzero order; percentage fees use the actual notional.
Both redistribution modes use positive target gaps, including orders initially
rounded to zero, and account for a flat fee when opening such an order.

DP maximizes spend at an adaptive integer scale; rounded-up costs can make it
conservative. Its capacity is at most 100,000 scaled units and total work/storage
at most 1,000,000 asset-capacity cells. Larger problems use greedy with the same
eligibility and fee policy. The DP result never leaves more cash than that
greedy baseline. Redistribution can overshoot individual target weights.

Errors:

- `422`: request validation failed; `base_currency` is mandatory.
- `502`: missing, malformed, stale or inconsistent quote/ECB data; body is `{"detail": "..."}`.
- `503`: configured cache unavailable, worker queue exhausted its budget, or request deadline exceeded.
- `429`: configured provider rate limit exceeded; `Retry-After` is exposed through CORS.

### `GET /v1/tickers/search`

Query parameters: `q` (trimmed string, 2..64 printable characters). Calls all configured search providers in parallel via `asyncio.gather` and merges results.

```json
{
  "results": [
    {"ticker": "VWCE.DE", "name": "YF · Vanguard FTSE All-World UCITS ETF",
     "exchange": "XETRA", "type": "ETF", "provider": "yahoo", "currency": "EUR"}
  ]
}
```

`type` is one of: `EQUITY`, `ETF`, `MUTUALFUND`, `CRYPTOCURRENCY`, `CURRENCY`. Indices, futures, and options are filtered out. `provider` and `currency` round-trip to `POST /v1/rebalance`.

Errors:

- `422`: `q` absent, too short/long or containing control characters
- `503`: all configured search providers failed (including quota errors); genuine empty matches return 200

### `GET /v1/config`

Returns the backend-owned currency policy consumed by the frontend at startup:

```json
{
  "base_currencies": ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD"]
}
```

`BASE_CURRENCY` is an ordered JSON list; the frontend uses its first item as the
initial selection and renders the full list.

### `GET /v1/health`, `GET /v1/ready`

- `/v1/health`: always `200` (liveness probe)
- `/v1/ready`: `200` unless `CACHE_BACKEND=redis` and `redis.ping()` fails (then `503`)

## Configuration

Read from `.env` (see [`.env.example`](../.env.example)):

| Variable | Default | Purpose |
|----------|---------|---------|
| `BASE_CURRENCY` | `["EUR","USD","GBP","CHF","JPY","CAD","AUD"]` | Ordered JSON list of three-letter portfolio currencies; the first is the initial selection and the full list is exposed through `GET /v1/config` |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `CACHE_BACKEND` | `local` | `local`: per-process dict; `redis`: shared across workers |
| `CACHE_TTL_SECONDS` | `300` | Positive price-cache TTL in seconds |
| `LOCAL_CACHE_MAX_ENTRIES` | `10000` | Positive capacity per local cache/rate store |
| `QUOTE_MAX_AGE_DAYS` | `7` | Accepted price observation age, 0..30 calendar days |
| `REDIS_TIMEOUT_SECONDS` | `2` | Redis connect/read timeout, >0 and <=30 seconds |
| `PROVIDER_TIMEOUT_SECONDS` | `10` | HTTP operation timeout, >0 and <=60 seconds |
| `PROVIDER_REQUEST_BUDGET_SECONDS` | `30` | Total worker budget including queue time, >0 and <=120 seconds |
| `PROVIDER_CONCURRENCY` | `8` | Maximum active provider workers per application, 1..32 |
| `FX_CACHE_TTL_SECONDS` | `3600` | ECB reference-observation cache TTL |
| `ECB_FX_MAX_AGE_DAYS` | `7` | Maximum accepted observation age in calendar days; stale data fails closed |
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

When `OTEL_ENABLED=true`, `app.core.telemetry.setup_telemetry` configures OTLP/HTTP exporters. The application uses OpenTelemetry ASGI middleware with its lifespan-owned SDKs for HTTP request spans.

### Metrics

| Name | Type | Unit | Labels |
|------|------|------|--------|
| `pestoengine_market_fetch_duration_seconds` | histogram | s | `provider` |
| `pestoengine_market_fetch_total` | counter | tickers | `provider`, `outcome` (`success` / `error`) |
| `pestoengine_cache_ops_total` | counter | ops | `backend` (`local` / `redis`), `result` (`hit` / `miss`) |
| `pestoengine_provider_errors_total` | counter | errors | `provider`, `error_type` (`explicit` / `fallback`) |
| `pestoengine_rebalance_duration_seconds` | histogram | s | `algorithm` (`greedy` / `dp` / `fractional`) |
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

The `_AccessLogMiddleware` (in `main.py`) emits one structured access log for every HTTP request, with `http_method`, `http_path`, `http_status`, `http_duration_ms`, `http_client`, `http_user_agent`, `http_version`. This includes rate-limit responses and CORS preflights. Rate-limit decisions are also counted by `pestoengine_rate_limit_total`. API keys and configured telemetry credentials are redacted from HTTP logs, owned console/OTLP handlers, exception text and structured fields.

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
ruff check app tests      # imports and basic correctness lint
```

Fixtures in `tests/conftest.py`:

- `mock_registry`: `MagicMock(spec=ProviderRegistry)`
- `mock_fx_provider`: `MagicMock(spec=EcbFxProvider)`
- `client`: `TestClient(app)` with both data dependencies overridden

Tests disable the personal `.env` and reject unmocked provider HTTP. Regression tests cover financial invariants, exhaustive small knapsack cases, atomic Redis behavior with fakeredis/Lua, middleware order, lifespan cleanup, timeouts and trace context. CI installs the universal lock files on Linux (Python 3.11/3.12) and Windows (Python 3.12).

## Calling the API

### curl

```bash
curl -X POST http://localhost:8000/v1/rebalance \
     -H "Content-Type: application/json" \
     -d '{"only_buy":true,"increment":1000,"base_currency":"EUR","assets":[{"ticker":"VWCE.DE","desired_percentage":100,"shares":0,"fees":0}]}' | jq
```

### Python (`httpx`)

```python
import httpx

payload = {
    "only_buy": True,
    "increment": 1000,
    "base_currency": "EUR",
    "optimal_redistribute": False,
    "assets": [
        {
            "ticker": "VWCE.DE",
            "provider": "yahoo",
            "currency": "EUR",
            "desired_percentage": 60,
            "shares": 10,
            "fees": 0.5,
            "percentage_fee": True,
        },
        {
            "ticker": "VAGF.DE",
            "provider": "yahoo",
            "currency": "EUR",
            "desired_percentage": 40,
            "shares": 5,
            "fees": 1.5,
            "percentage_fee": False,
        },
    ],
}

response = httpx.post("http://localhost:8000/v1/rebalance", json=payload)
response.raise_for_status()
print(response.json())
```
