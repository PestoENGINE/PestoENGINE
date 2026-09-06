"""Redis-backed cache implementation."""

import json
from collections.abc import Callable
from typing import TypeVar

from redis import Redis, RedisError

from app.core.exceptions import CacheUnavailableError
from app.core.redis_client import create_redis_client
from app.market_data.cache import AbstractCache

T = TypeVar("T")


class RedisCache(AbstractCache[T]):
    """Atomic SETEX writes; transport failures become CacheUnavailableError.

    The application supplies its lifespan-owned client. Standalone callers
    that omit it own the client's lifecycle through this cache instance.
    """

    def __init__(
        self,
        url: str,
        ttl_seconds: int,
        *,
        encode: Callable[[T], object],
        decode: Callable[[object], T],
        client: Redis | None = None,
    ) -> None:
        self._client = client if client is not None else create_redis_client(url)
        self._ttl = ttl_seconds
        self._encode = encode
        self._decode = decode

    def get(self, key: str) -> T | None:
        try:
            raw = self._client.get(key)
        except RedisError as exc:
            raise CacheUnavailableError("Redis cache read failed") from exc
        if raw is None:
            return None
        try:
            return self._decode(json.loads(raw))
        except (TypeError, ValueError):
            return None

    def set(self, key: str, value: T) -> None:
        try:
            self._client.setex(key, self._ttl, json.dumps(self._encode(value)))
        except RedisError as exc:
            raise CacheUnavailableError("Redis cache write failed") from exc
