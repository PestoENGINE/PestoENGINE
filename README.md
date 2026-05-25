<div align="center">

<img src="brand-logo.svg" alt="PestoENGINE – Portfolio Rebalancing" width="520" />

**Rebalancing execution engine for passive investors**

You know your allocation. Now know exactly what to buy.

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com/)
[![Svelte 5](https://img.shields.io/badge/Svelte-5-FF3E00.svg)](https://svelte.dev/)

**[Live Demo → pestoengine.onrender.com](https://pestoengine.onrender.com)**

</div>

Enter your targets, current holdings, and the cash you want to deploy. PestoENGINE returns the exact number of shares to buy per asset, with your broker's fee structure already priced in, allocation drift shown, and leftover change made explicit. Same inputs always produce the same output.

No accounts. No data stored. Self-hostable. MIT licensed.

## How it works

**01 - Set your target allocation**  
Enter each ticker, your target weight, current share count, and your broker's fee. Live prices are fetched from the configured market data providers at calculation time.

**02 - Drop in your monthly cash**  
Enter the cash you want to deploy this period. Enable buy-only mode to ensure PestoENGINE never triggers a sale. Enable knapsack mode to maximise cash deployment.

**03 - Get the exact buy order**  
PestoENGINE returns the exact number of shares to buy per asset. Deterministic, explainable, verifiable.

## Algorithm modes

| Mode | When to use |
|------|-------------|
| **Greedy** `O(n log n)` | Speed matters; some leftover tolerance is acceptable. |
| **Knapsack DP** `O(n × W)` | Cash efficiency matters; minimises leftover change. |
| **Buy-only** `O(n)` | Rebalancing without adding capital; set `only_buy: true`. |

The algorithm is not proprietary. The source is in [`app/rebalance/rebalance.py`](app/rebalance/rebalance.py). Every formula is readable and every result is verifiable by hand.

## Architecture

One deployable: FastAPI backend serves both the JSON API and the Svelte SPA (built as static files) on port 8000. One container, one process.

| Component | Stack | Detailed docs |
|-----------|-------|---------------|
| Backend | FastAPI, Python 3.11+, Pydantic v2, httpx, OpenTelemetry | [`app/README.md`](app/README.md) |
| Frontend | Svelte 5, TypeScript, Tailwind CSS v4, Vite | [`ui/README.md`](ui/README.md) |
| Market data | Yahoo Finance, Alpha Vantage (configurable fallback), cached 5 minutes | [`app/README.md`](app/README.md) |

## Prerequisites

- **Docker** (recommended): Docker Desktop or Docker Engine
- **Manual**: Python 3.11+, Node.js 20+

## Quick start

### Docker

```bash
docker run -d \
  --name pestoengine \
  -p 8000:8000 \
  ghcr.io/pestoengine/pestoengine:latest
```

### Manual

```bash
git clone https://github.com/PestoENGINE/PestoENGINE
cd PestoENGINE && cp .env.example .env

# Backend
python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd ui && npm install
npm run dev
```

For backend details (API reference, configuration, observability, tests) see [`app/README.md`](app/README.md).  
For frontend details (structure, state, build) see [`ui/README.md`](ui/README.md).

## Stack

- **Backend**: FastAPI, Python 3.11+, Pydantic v2, httpx, OpenTelemetry
- **Frontend**: Svelte 5, TypeScript, Tailwind CSS v4, Vite
- **Market data**: Yahoo Finance and Alpha Vantage (configurable fallback chain), cached 5 minutes (local in-memory or Redis)
- **Observability**: OTLP/HTTP export of metrics, traces, and logs (Loki-compatible via Grafana Alloy)

---

*A financial tool must be auditable. So the algorithm is public.*
