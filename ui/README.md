# PestoENGINE – Frontend

Svelte 4 + TypeScript single-page application. Communicates with the backend via
a single endpoint (`POST /v1/rebalance`) and a ticker search endpoint (`GET /v1/tickers/search`).

## Structure

```
ui/
├── src/
│   ├── App.svelte        # Root component (state, rebalance call, dark mode)
│   ├── app.css           # Global styles and design tokens
│   ├── storage.ts        # localStorage persistence
│   ├── types.ts          # TypeScript interfaces
│   └── components/       # UI components (header, hero, editor, results, static sections)
├── public/               # Static assets (favicon, brand logo)
└── index.html            # Entry point
```

## Design system

Global CSS tokens are defined in `app.css` under `:root` and `html.dark`:

- **Teal palette** - `--teal`, `--teal-hover`, `--teal-light`, `--teal-mid`
- **Hero surface** - `--hero-bg`, `--hero-text`, `--hero-sub`, `--hero-border`
- **Typography** - `--sans` (Geist), `--mono` (Geist Mono) via Google Fonts

## Development

```bash
npm install
npm run dev
```

UI available at `http://localhost:5173`.

Vite proxies all `/v1/*` requests to `http://localhost:8000` in dev mode - no
CORS configuration needed. The backend must be running concurrently.

## Production build

```bash
npm run build
# Output: dist/
```

The bundle can be served by any static file server. If the frontend and backend
are deployed on different origins, set `CORS_ORIGINS` in the backend `.env`.
