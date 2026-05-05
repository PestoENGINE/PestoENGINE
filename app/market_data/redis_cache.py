"""Redis-backed cache implementation."""

from app.market_data.cache import AbstractCache


class RedisCache(AbstractCache):
    """Redis cache using ``SETEX`` for atomic write-with-TTL.

    The ``redis`` package is imported lazily so deployments using
    ``CACHE_BACKEND=local`` do not require the package to be installed.
    """

    def __init__(self, url: str, ttl_seconds: int) -> None:
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

    def get(self, key: str) -> float | None:
        raw = self._client.get(key)
        return float(raw) if raw is not None else None

    def set(self, key: str, value: float) -> None:
        self._client.setex(key, self._ttl, value)
