"""Redis-backed rate limit store."""

from redis import Redis

from app.rate_limit.base import AbstractRateLimitStore


class RedisRateLimitStore(AbstractRateLimitStore):
    """Atomically increment and set/repair TTL in the same Redis operation."""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._increment = client.register_script("""
            local count = redis.call('INCR', KEYS[1])
            if count == 1 or redis.call('TTL', KEYS[1]) < 0 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return count
        """)

    def increment(self, key: str, window_seconds: int) -> int:
        if window_seconds <= 0:
            raise ValueError("Window must be positive")
        return int(self._increment(keys=[key], args=[window_seconds]))
