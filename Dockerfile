# Stage 1: UI builder
FROM node:22-alpine AS ui-builder
WORKDIR /ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Stage 2: Python dependency builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS py-builder
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    uv venv .venv && \
    uv pip install --python .venv/bin/python -r requirements.txt

# Remove test directories before compiling (avoid generating bytecode for code we discard)
RUN find .venv/lib -type d \( -name "tests" -o -name "test" \) -prune -exec rm -rf {} + 2>/dev/null || true

# Compile .py -> .pyc in-place (-b places .pyc next to source, not in __pycache__).
# Required: without -b, Python does not import .pyc when the .py source is absent.
RUN python -m compileall -b -q .venv/lib && \
    find .venv/lib -type f -name "*.py" -delete && \
    find .venv/lib -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true && \
    find .venv/lib -type d \( -name "*.dist-info" -o -name "*.egg-info" \) -prune -exec rm -rf {} + 2>/dev/null || true && \
    find .venv/lib -type f -name "*.pyi" -delete

# Stage 3: Runtime
FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --from=py-builder --chown=app:app /app/.venv .venv
COPY --chown=app:app --from=ui-builder /ui/dist ./ui/dist
COPY --chown=app:app app/ ./app/

USER app

RUN python -m compileall -b -q app/ && \
    find app/ -type f -name "*.py" -delete && \
    find app/ -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
