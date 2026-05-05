"""Abstract cache interface and local in-memory implementation."""

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable


class AbstractCache(ABC):
    @abstractmethod
    def get(self, key: str) -> float | None: ...

    @abstractmethod
    def set(self, key: str, value: float) -> None: ...


class LocalCache(AbstractCache):
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
    ) -> None:
        self._store: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._clock = clock

    def get(self, key: str) -> float | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._clock() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: float) -> None:
        with self._lock:
            self._store[key] = (value, self._clock() + self._ttl)
