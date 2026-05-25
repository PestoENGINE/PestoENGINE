"""Redis-backed rate limit store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.rate_limit.base import AbstractRateLimitStore

if TYPE_CHECKING:
    import redis as _redis


class RedisRateLimitStore(AbstractRateLimitStore):
    """Redis-backed rate limit store using INCR + EXPIRE.

    INCR and EXPIRE are two separate commands. If the process crashes between
    them, the key has no TTL and will leak until manually removed. For a
    deterrent-only rate limiter this risk is accepted; use a Lua pipeline if
    strict atomicity is required.
    """

    def __init__(self, client: "_redis.Redis") -> None:
        self._client = client

    def increment(self, key: str, window_seconds: int) -> int:
        count = self._client.incr(key)
        if count == 1:
            self._client.expire(key, window_seconds)
        return count
