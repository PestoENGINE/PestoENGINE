"""Bound provider work, retain trace context, and track threads until completion."""

import asyncio
import time
from collections.abc import Callable
from contextvars import copy_context
from functools import partial
from typing import TypeVar

from fastapi import HTTPException

from app.api.resources import AppResources
from app.core.exceptions import ProviderDeadlineError
from app.core.http import provider_budget, remaining_budget

T = TypeVar("T")


async def run_provider_work(
    resources: AppResources, function: Callable[..., T], *args, **kwargs
) -> T:
    budget = resources.settings.provider_request_budget_seconds
    deadline = time.monotonic() + budget
    try:
        await asyncio.wait_for(resources.semaphore.acquire(), timeout=budget)
    except TimeoutError as exc:
        raise HTTPException(503, "Market data workers are busy") from exc
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        resources.semaphore.release()
        raise HTTPException(503, "Market data request deadline exceeded")
    context = copy_context()

    def execute() -> T:
        with provider_budget(max(0, deadline - time.monotonic())):
            remaining_budget()
            return function(*args, **kwargs)

    loop = asyncio.get_running_loop()
    try:
        future = loop.run_in_executor(None, partial(context.run, execute))
    except BaseException:
        resources.semaphore.release()
        raise
    resources.pending_work.add(future)

    def finished(done: asyncio.Future) -> None:
        resources.pending_work.discard(done)
        resources.semaphore.release()
        if not done.cancelled():
            done.exception()  # Retrieve late failures after an HTTP timeout/cancellation.

    future.add_done_callback(finished)
    try:
        # A timed-out thread still occupies its slot until it actually finishes.
        return await asyncio.wait_for(asyncio.shield(future), timeout=remaining)
    except (TimeoutError, ProviderDeadlineError) as exc:
        raise HTTPException(503, "Market data request deadline exceeded") from exc
