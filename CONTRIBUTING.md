# Contributing to PestoENGINE

Thanks for your interest. This document covers setup, conventions, and the review workflow used in this repository.

## Quick orientation

- Architecture and project goals: [`README.md`](README.md)
- Backend setup, API reference, observability, tests: [`app/README.md`](app/README.md)
- Frontend setup, build, typecheck: [`ui/README.md`](ui/README.md)

Read these first.

## Development setup

Backend and frontend run as two separate processes during development. Full instructions are in the READMEs above.

Short version:

```bash
git clone https://github.com/PestoENGINE/PestoENGINE
cd PestoENGINE && cp .env.example .env

# Backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd ui && npm install && npm run dev
```

### Updating Python dependencies

Edit `requirements.in` or `requirements-dev.in`, then regenerate the committed
universal lock files (Python 3.11+) with:

```bash
uv pip compile requirements.in --universal --python-version 3.11 -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 -o requirements-dev.txt
```

Do not edit the generated `requirements*.txt` files by hand. Use `--upgrade` to
refresh every dependency, or `--upgrade-package <name>` for one dependency.

## Running tests and checks

Backend (Python):

```bash
pytest                    # all tests
pytest tests/unit         # unit only
pytest tests/integration  # integration only
pytest -q --tb=short      # CI style
```

On Windows, run pytest through the venv interpreter to guarantee project deps:

```powershell
venv\Scripts\python.exe -m pytest --tb=short -q
```

Frontend (TypeScript / Svelte):

```bash
cd ui
npm run check    # svelte-check + tsc; runs in CI as test-frontend
npm run build    # production build to ui/dist/
```

CI runs both jobs on every push and PR (`.github/workflows/ci.yml`).

## Code conventions

### Python (`app/`, `tests/`)

- Type hints on all public functions.
- Pydantic v2 schemas at the HTTP boundary only. Do not add validation in service or algorithm layers when schema and service errors are already readable.
- Pure functions in `app/rebalance/` stay pure: no logging, no I/O, no global state.
- Use `httpx` (sync) for outbound HTTP. Wrap blocking calls in `loop.run_in_executor` from async routes.
- Use the standard `logging` module; pass structured fields via `extra={...}` so the JSON formatter (`app/core/log_config.py`) picks them up. OTel `trace_id` and `span_id` are injected automatically when a span is active.
- Custom OTel spans live in the layer that owns the operation. Follow the existing naming: `rebalance_compute`, `cache_lookup`, `market_fetch`.

### TypeScript / Svelte (`ui/`)

- Svelte 5 with the legacy API (`$:` reactive declarations, `on:event`, `createEventDispatcher`). Do not introduce runes (`$state`, `$derived`) unless intentionally migrating a whole component.
- State for the rebalance flow lives in `App.svelte`. Children emit events upward via `createEventDispatcher`.
- Persisted state goes through `src/storage.ts`. Bump the `version` field in `PortfolioExport` whenever the import/export shape changes.
- Use the CSS custom properties in `src/app.css` (`--teal`, `--surface`, etc.) rather than hardcoded colors.

## Commit messages

This repository uses [Conventional Commits](https://www.conventionalcommits.org/) with optional scopes. Subject in lowercase imperative, no trailing period.

Format:

```
<type>(<scope>): <subject>
```

Types in use:

| Type | When |
|------|------|
| `feat` | New user-facing feature or new API surface |
| `fix` | Bug fix |
| `perf` | Performance change with no behavior change |
| `refactor` | Code restructuring without behavior change |
| `docs` | Documentation only |
| `chore` | Dependencies, build, cleanup, no app code change |
| `test` | Tests only |
| `ci` | CI configuration |

Common scopes: `observability`, `market-data`, `rebalance`, `api`, `ui`.

Examples from this repo:

```
feat(observability): add custom spans to rebalance pipeline
perf(observability): refine fetch duration histogram buckets below 100ms
chore: remove yfinance dead code and commented deps
docs: align READMEs with current stack
```

Keep the subject under 72 characters. Use the body for context and rationale when the diff is not self-explanatory.

## Pull requests

1. Fork the repository and branch from `master`.
2. Make sure `pytest` and `npm run check` pass locally.
3. Open the PR against `master`. CI (`.github/workflows/ci.yml`) must be green.
4. A maintainer will review and merge. Squash WIP commits before requesting review.

## Reporting issues

Use the GitHub issue tracker. Include:

- What you did
- What you expected
- What actually happened (HTTP status, error message, log snippet)
- Environment: Docker image tag or git commit, `CACHE_BACKEND` value, `MARKET_DATA_PROVIDERS` value

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE) of this project.
