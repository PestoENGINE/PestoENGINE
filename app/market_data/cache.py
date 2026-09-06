"""Abstract cache interface and local in-memory implementation."""

import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class AbstractCache(ABC, Generic[T]):
    @abstractmethod
    def get(self, key: str) -> T | None: ...

    @abstractmethod
    def set(self, key: str, value: T) -> None: ...


class LocalCache(AbstractCache[T]):
    """Thread-safe in-memory cache with TTL.

    Two invariants:
    - ``get`` returns ``None`` for both missing and expired keys; the caller
      cannot distinguish between the two cases.
    - Expiry is stamped at ``set`` time, not at ``get`` time.
    """

    def __init__(
        self,
        ttl_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        *,
        max_entries: int = 10_000,
    ) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("Cache TTL and capacity must be positive")
        self._store: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self._max_entries = max_entries
        self._next_cleanup = 0.0
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._clock = clock

    def _cleanup(self, now: float) -> None:
        if now >= self._next_cleanup:
            for key in [k for k, (_, expires) in self._store.items() if now >= expires]:
                del self._store[key]
            self._next_cleanup = now + min(self._ttl, 60)

    def get(self, key: str) -> T | None:
        with self._lock:
            now = self._clock()
            self._cleanup(now)
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if now >= expires_at:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: T) -> None:
        with self._lock:
            now = self._clock()
            self._cleanup(now)
            self._store[key] = (value, now + self._ttl)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)
