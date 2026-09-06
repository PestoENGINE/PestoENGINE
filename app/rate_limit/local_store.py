"""Thread-safe in-process rate limit store with TTL."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable

from app.rate_limit.base import AbstractRateLimitStore


class LocalRateLimitStore(AbstractRateLimitStore):
    """Bounded, expiring counters; each process has its own quota.

    Expired epoch-minute buckets are reclaimed even if never accessed again.
    At capacity the oldest bucket is evicted (this is a deterrent limiter).
    Use Redis for a shared quota across workers.
    """

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, *, max_entries: int = 10_000
    ) -> None:
        if max_entries <= 0:
            raise ValueError("Capacity must be positive")
        self._data: OrderedDict[str, tuple[int, float]] = OrderedDict()
        self._max_entries = max_entries
        self._next_cleanup = 0.0
        self._lock = threading.Lock()
        self._clock = clock

    def increment(self, key: str, window_seconds: int) -> int:
        if window_seconds <= 0:
            raise ValueError("Window must be positive")
        now = self._clock()
        with self._lock:
            if now >= self._next_cleanup:
                for old in [k for k, (_, expiry) in self._data.items() if now >= expiry]:
                    del self._data[old]
                self._next_cleanup = now + min(window_seconds, 60)
            count, expires_at = self._data.get(key, (0, 0.0))
            if now >= expires_at:
                count = 0
                expires_at = now + window_seconds
            count += 1
            self._data[key] = (count, expires_at)
            while len(self._data) > self._max_entries:
                self._data.popitem(last=False)
            return count
