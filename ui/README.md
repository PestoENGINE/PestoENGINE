# PestoENGINE – Frontend

Single-page application that consumes the backend runtime configuration, `POST /v1/rebalance`, and `GET /v1/tickers/search`. Renders the input editor, calls the backend, and displays the resulting buy/sell orders. Persists state in `localStorage` only; no server-side storage.

## Stack

| Layer | Library | Version |
|-------|---------|---------|
| UI framework | Svelte | `^5.56.3` (components use the Svelte 4 compatible API: `$:` reactive statements, `createEventDispatcher`, `on:event` directives; no runes) |
| Language | TypeScript | `~6.0.3` |
| Styling | Hand-written CSS | Global `src/app.css` holds only cross-component concerns (reset, design tokens, shared primitives, the two table systems); each component owns its single-use styles in a scoped `<style>` block |
| Build tool | Vite | `^8.1.0` |
| Svelte plugin | `@sveltejs/vite-plugin-svelte` | `^7.1.2` |
| Typecheck | `svelte-check` + `tsc` | `^4.7.0` / `~6.0.3` |
| Tests | Vitest | `^4.1.9` (unit tests for the plain-TS logic modules) |

## Structure

```
ui/
├── index.html       # Entry HTML; restores dark mode + language pre-hydration
├── vite.config.ts   # svelte plugin; dev proxy /v1/* to http://localhost:8000
├── public/          # Static assets (favicon, brand logo, robots)
├── src/
│   ├── main.ts        # Mounts <App />
│   ├── App.svelte     # Root: state, API call, import/export, dark mode
│   ├── app.css        # reset, design tokens, shared primitives, table systems
│   ├── storage.ts     # localStorage I/O (versioned, validated)
│   ├── types.ts       # Asset, Settings, RebalanceResponse, PortfolioExport, UiError
│   ├── i18n/          # Hand-rolled i18n: locale store, t/tx, en.json + it.json
│   └── components/    # Header, Hero, GlobalSettings, PortfolioEditor, AssetRow,
│                      # TickerAutocomplete, ResultsPanel, AssetResult, ...
└── dist/            # Production build (gitignored; built by Vite, served by FastAPI from /)
```

## State management

All state lives in `App.svelte` (Svelte 4 compatible reactivity: `let` + assignments + `$:` for derived values; child to parent communication via `createEventDispatcher`). Three localStorage keys (see `src/storage.ts`):

| Key | Type | Default |
|-----|------|---------|
| `pesto_engine_settings` | `{ increment, baseCurrency, onlyBuy, optimalRedistribute, fractionalShares }` | `{ 1000, BASE_CURRENCY, true, false, false }`, where `BASE_CURRENCY` comes from `/v1/config` |
| `pesto_engine_assets` | `Asset[]` (`id`, `ticker`, `provider`, `currency`, `desiredPercentage`, `shares`, `fees`, `percentageFee`) | `[]` |
| `pesto_engine_dark_mode` | `boolean` | `false` |
| `pesto_engine_locale` | `'en' \| 'it'` | auto-detected from `navigator.language`, else `en` |

Dark mode class (`html.dark`) and `<html lang>` are set inline in `index.html` before Svelte hydrates to avoid a flash of the wrong theme/language.

## Internationalization (i18n)

UI strings are translated with a small hand-rolled module in `src/i18n/` (no library):

- `en.json` / `it.json` hold the dictionaries; `en.json` is the source of truth for the key set. A test asserts `it.json` defines exactly the same keys.
- `index.ts` exposes a `locale` store, a reactive translator `t` used in markup as `{$t('settings.onlyBuy')}`, and an imperative `tx(...)` for non-reactive code (`confirm()`, `document.title`). Missing keys fall back to English, then to the raw key, so a partial translation degrades gracefully.
- Components reference keys via `$t`; the framework-agnostic logic modules (`api.ts`, `portfolio-io.ts`) stay language-free by returning a `UiError`: `{ kind: 'key', ... }` (one translated message), `{ kind: 'validation', items }` (a list of translated messages mapped from a 422's stable `type`/`loc`), or `{ kind: 'raw', text }` (verbatim passthrough, now only for an upstream-limiter 429 that omits `Retry-After`).
- The choice persists in `localStorage` (`pesto_engine_locale`) and switches live from the header.

**Adding a language** is two steps: drop an `xx.json` next to the existing ones, then add a single entry to the `LOADERS` map in `index.ts` (`xx: () => import('./xx.json').then((m) => m.default)`). That map is the single source of truth: the `Locale` type, the `LOCALES` list, browser-language auto-detection (`navigator.language` is matched by prefix), persistence, and the key-parity test all derive from it. Anything left untranslated falls back to English, so a partial translation lands incrementally.

**Translated:** backend errors are localized on the client by mapping their stable codes, not by translating prose: the Pydantic `type`/`loc` of a 422, the `Retry-After` of a 429, and a generic message for a 502. **Not translated:** on-screen code (the JSON request sample, the docker command, complexity notations, file paths, ticker examples), the `PestoENGINE` name, and the rare upstream-limiter 429 prose that arrives without a `Retry-After`.

## Backend integration

| Endpoint | Method | Triggered by |
|----------|--------|--------------|
| `/v1/config` | `GET` | Before mounting the SPA; supplies the ordered base-currency list |
| `/v1/rebalance` | `POST` | "Calculate buy order" button in `PortfolioEditor` |
| `/v1/tickers/search?q=` | `GET` | Live as the user types in `TickerAutocomplete` |

Error mapping in `App.svelte:runRebalance`:

| Backend status | UI behavior |
|----------------|-------------|
| `200` | Render `ResultsPanel`, scroll to `#results` |
| `422` | Map each `detail[]` item (its stable `type` + `loc`) to a translated message; unknown types fall back to a generic translated wrapper around the backend `msg` |
| `429` | Translated "Too many requests" message, with seconds from `Retry-After` when present (a string `detail` without the header is passed through verbatim) |
| `502` | Translated generic quote/ECB-data message (`errors.marketData`) |
| other / network | Translated generic "Request failed" message |

Request payload converts UI camelCase to backend snake_case:

| UI field | Backend field |
|----------|---------------|
| `desiredPercentage` | `desired_percentage` |
| `percentageFee` | `percentage_fee` |
| `onlyBuy` | `only_buy` |
| `optimalRedistribute` | `optimal_redistribute` |
| `fractionalShares` | `fractional_shares` |
| `baseCurrency` | `base_currency` |
| `assets[].currency` | `assets[].currency` |

## Import / Export

`PortfolioExport` JSON format (versioned, validated by `App.svelte:processImport`):

```json
{
  "version": 2,
  "exportedAt": "2026-07-20T10:30:00Z",
  "settings": { "increment": 1000, "baseCurrency": "EUR", "onlyBuy": true, "optimalRedistribute": false, "fractionalShares": false },
  "assets": [
    { "ticker": "VWCE.DE", "provider": "yahoo", "currency": "EUR", "desiredPercentage": 100, "shares": 10, "fees": 0.5, "percentageFee": true }
  ]
}
```

Only version 2 is accepted. `baseCurrency` is mandatory and must be one of the
currencies returned by `GET /v1/config`; version 1 is rejected because
migrating it would require guessing a portfolio currency. Version 2 persists
both base and per-asset quote currency.

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
