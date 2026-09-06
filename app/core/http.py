"""Shared provider HTTP limits and a deadline propagated into worker threads."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import httpx

from app.core.exceptions import MarketDataError, ProviderDeadlineError

_deadline: ContextVar[float | None] = ContextVar("provider_deadline", default=None)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@contextmanager
def provider_budget(seconds: float) -> Iterator[None]:
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def remaining_budget() -> float | None:
    deadline = _deadline.get()
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProviderDeadlineError("Market data request deadline exceeded")
    return remaining


def provider_get(
    client: httpx.Client | None, url: str, *, timeout: float, **kwargs
) -> httpx.Response:
    remaining = remaining_budget()
    timeout = min(timeout, remaining) if remaining is not None else timeout
    if client is None:
        # Standalone providers remain usable without owning a persistent client.
        response = httpx.get(url, timeout=timeout, **kwargs)
        remaining_budget()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise MarketDataError("Market data response exceeds the size limit")
        return response
    with client.stream("GET", url, timeout=timeout, **kwargs) as response:
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            remaining_budget()
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise MarketDataError("Market data response exceeds the size limit")
        # iter_bytes already decoded compression; do not decode the body twice.
        headers = dict(response.headers)
        headers.pop("content-encoding", None)
        headers.pop("content-length", None)
        remaining_budget()
        return httpx.Response(
            response.status_code, content=bytes(body), headers=headers, request=response.request
        )


def retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def retry_pause(seconds: float) -> None:
    remaining = remaining_budget()
    if remaining is not None and remaining <= seconds:
        raise ProviderDeadlineError("Market data request deadline exceeded")
    time.sleep(seconds)


def safe_error(exc: Exception) -> str:
    return (
        f"HTTP {exc.response.status_code}"
        if isinstance(exc, httpx.HTTPStatusError)
        else type(exc).__name__
    )
