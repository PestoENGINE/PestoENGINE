"""Redis-backed rate limit store."""

from redis import Redis

from app.rate_limit.base import AbstractRateLimitStore


class RedisRateLimitStore(AbstractRateLimitStore):
    """Redis-backed rate limit store using INCR + EXPIRE.

    INCR and EXPIRE are two separate commands. If the process crashes between
    them, the key has no TTL and will leak until manually removed. For a
    deterrent-only rate limiter this risk is accepted; use a Lua pipeline if
    strict atomicity is required.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    def increment(self, key: str, window_seconds: int) -> int:
        count = self._client.incr(key)
        if count == 1:
            self._client.expire(key, window_seconds)
        return count
