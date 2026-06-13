# PestoENGINE – Frontend

Single-page application that consumes `POST /v1/rebalance` and `GET /v1/tickers/search`. Renders the input editor, calls the backend, and displays the resulting buy/sell orders. Persists state in `localStorage` only; no server-side storage.

## Stack

| Layer | Library | Version |
|-------|---------|---------|
| UI framework | Svelte | `^5.55.4` (components use the Svelte 4 compatible API: `$:` reactive statements, `createEventDispatcher`, `on:event` directives; no runes) |
| Language | TypeScript | `~6.0.2` |
| Styling | Hand-written CSS | Global `src/app.css` holds only cross-component concerns (reset, design tokens, shared primitives, the two table systems); each component owns its single-use styles in a scoped `<style>` block |
| Build tool | Vite | `^8.0.10` |
| Svelte plugin | `@sveltejs/vite-plugin-svelte` | `^7.0.0` |
| Typecheck | `svelte-check` + `tsc` | `^4.4.6` / `~6.0.2` |
| Tests | Vitest | `^4.1.7` (unit tests for the plain-TS logic modules) |

## Structure

```
ui/
├── index.html       # Entry HTML; restores dark mode pre-hydration
├── vite.config.ts   # svelte plugin; dev proxy /v1/* to http://localhost:8000
├── public/          # Static assets (favicon, brand logo, robots)
├── src/
│   ├── main.ts        # Mounts <App />
│   ├── App.svelte     # Root: state, API call, import/export, dark mode
│   ├── app.css        # reset, design tokens, shared primitives, table systems
│   ├── storage.ts     # localStorage I/O (versioned, validated)
│   ├── types.ts       # Asset, Settings, RebalanceResponse, PortfolioExport
│   └── components/    # Header, Hero, GlobalSettings, PortfolioEditor, AssetRow,
│                      # TickerAutocomplete, ResultsPanel, AssetResult, ...
└── dist/            # Production build (gitignored; built by Vite, served by FastAPI from /)
```

## State management

All state lives in `App.svelte` (Svelte 4 compatible reactivity: `let` + assignments + `$:` for derived values; child to parent communication via `createEventDispatcher`). Three localStorage keys (see `src/storage.ts`):

| Key | Type | Default |
|-----|------|---------|
| `pesto_engine_settings` | `{ increment, onlyBuy, optimalRedistribute, fractionalShares }` | `{ 1000, true, false, false }` |
| `pesto_engine_assets` | `Asset[]` (`id`, `ticker`, `provider`, `desiredPercentage`, `shares`, `fees`, `percentageFee`) | `[]` |
| `pesto_engine_dark_mode` | `boolean` | `false` |

Dark mode class (`html.dark`) is set inline in `index.html` before Svelte hydrates to avoid a flash of light theme.

## Backend integration

| Endpoint | Method | Triggered by |
|----------|--------|--------------|
| `/v1/rebalance` | `POST` | "Calculate buy order" button in `PortfolioEditor` |
| `/v1/tickers/search?q=` | `GET` | Live as the user types in `TickerAutocomplete` |

Error mapping in `App.svelte:runRebalance`:

| Backend status | UI behavior |
|----------------|-------------|
| `200` | Render `ResultsPanel`, scroll to `#results` |
| `422` | Display `"Validation error: ..."` (formats `detail[].msg`) |
| `429` | Display backend `detail`, or "Too many requests. Try again in N seconds." derived from `Retry-After` |
| `502` | Display backend `detail` (typically `MarketDataError` message) |
| other / network | Generic `"Request failed"` message |

Request payload converts UI camelCase to backend snake_case:

| UI field | Backend field |
|----------|---------------|
| `desiredPercentage` | `desired_percentage` |
| `percentageFee` | `percentage_fee` |
| `onlyBuy` | `only_buy` |
| `optimalRedistribute` | `optimal_redistribute` |
| `fractionalShares` | `fractional_shares` |

## Import / Export

`PortfolioExport` JSON format (versioned, validated by `App.svelte:processImport`):

```json
{
  "version": 1,
  "exportedAt": "2026-05-25T10:00:00Z",
  "settings": { "increment": 1000, "onlyBuy": true, "optimalRedistribute": false, "fractionalShares": false },
  "assets": [
    { "ticker": "VOO", "provider": null, "desiredPercentage": 60, "shares": 10, "fees": 0.5, "percentageFee": true }
  ]
}
```

Sample portfolio: [`../portfolios/portfolio.json`](../portfolios/portfolio.json).

## Design tokens

Defined in `src/app.css` under `:root` (light) and `html.dark` (dark). Components reference them via `var(--token)`. Categories:

- Background / surface: `--bg`, `--surface`
- Border: `--border`
- Text: `--text`, `--text-2`, `--text-3`
- Brand teal: `--teal`, `--teal-hover`, `--teal-light`
- Error: `--error`, `--error-bg`, `--error-border`
- Hero dark surface: `--hero-bg`, `--hero-text`, `--hero-sub`, `--hero-border`
- Layout: `--nav-height`, `--panel-gap`
- Typography: `--sans` (Geist), `--mono` (Geist Mono); loaded from Google Fonts in `index.html`

## Setup

```bash
npm install
```

## Run (dev)

```bash
npm run dev
```

UI at `http://localhost:5173`. Vite proxies `/v1/*` to `http://localhost:8000`, so the backend must be running on port 8000. No CORS configuration is needed in dev.

## Build

```bash
npm run build       # output: dist/
npm run preview     # serve dist/ locally for verification
```

`dist/` is gitignored, not committed. In production it is produced by the Docker multi-stage build (stage `ui-builder` in [`../Dockerfile`](../Dockerfile)) and served by FastAPI from `/`; locally, `npm run build` regenerates it for `npm run preview`.

## Typecheck

```bash
npm run check
```

Runs `svelte-check` (using `tsconfig.app.json`) plus `tsc -p tsconfig.node.json`. Part of CI (`.github/workflows/ci.yml`, job `test-frontend`).

## Tests

```bash
npm run test         # run once (CI)
npm run test:watch   # watch mode
```

Vitest unit tests cover the framework-agnostic logic extracted from `App.svelte`:
`api.ts` (request body mapping and HTTP error-message mapping) and `portfolio-io.ts`
(import validation and the export round-trip). The component keeps only state and
event wiring, so the testable logic lives in plain `.ts` modules (`*.test.ts`
alongside them). Also part of CI.

## Deployment

In production, FastAPI mounts `ui/dist/` at `/` (see `_mount_ui` in [`../app/main.py`](../app/main.py)). The same uvicorn process serves both the API (`/v1/*`) and the SPA, so the frontend is reachable at the same origin as the API; no CORS configuration is needed.

When deploying frontend and backend on different origins, set `CORS_ORIGINS` in the backend `.env`.
