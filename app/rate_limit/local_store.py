"""Thread-safe in-process rate limit store with TTL."""

import threading
import time
from collections.abc import Callable

from app.rate_limit.base import AbstractRateLimitStore


class LocalRateLimitStore(AbstractRateLimitStore):
    """TTL-based cleanup only fires when the SAME key is accessed after expiry.

    With the middleware's epoch-minute key scheme each key is unique per minute
    and never reused, so _data grows proportionally to unique IPs * uptime.
    Acceptable for deterrent-only use on low-traffic deployments.

    This store is per-process. With multiple uvicorn workers the effective limit
    is N * RATE_LIMIT_PROVIDERS_PER_MIN. Use RedisRateLimitStore for a shared
    counter across workers.
    """
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def increment(self, key: str, window_seconds: int) -> int:
        now = self._clock()
        with self._lock:
            count, expires_at = self._data.get(key, (0, 0.0))
            if now >= expires_at:
                count = 0
                expires_at = now + window_seconds
            count += 1
            self._data[key] = (count, expires_at)
            return count
