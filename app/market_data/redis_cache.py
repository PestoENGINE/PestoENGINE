"""Redis-backed cache implementation."""

import json
from collections.abc import Callable
from typing import TypeVar

from app.market_data.cache import AbstractCache

T = TypeVar("T")


class RedisCache(AbstractCache[T]):
    """Redis cache using ``SETEX`` for atomic write-with-TTL.

    The ``redis`` package is imported lazily so deployments using
    ``CACHE_BACKEND=local`` do not require the package to be installed.
    """

    def __init__(
        self,
        url: str,
        ttl_seconds: int,
        *,
        encode: Callable[[T], object],
        decode: Callable[[object], T],
    ) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "redis package not found. "
                "Ensure redis>=5 is installed (it is listed in requirements.txt). "
                "If running in a custom environment, install it manually: pip install redis>=5"
            ) from exc
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds
        self._encode = encode
        self._decode = decode

    def get(self, key: str) -> T | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return self._decode(json.loads(raw))
        except (TypeError, ValueError):
            return None

    def set(self, key: str, value: T) -> None:
        self._client.setex(key, self._ttl, json.dumps(self._encode(value)))
