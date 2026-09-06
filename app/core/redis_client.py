"""Construct Redis clients with bounded I/O and no implicit retry backoff."""

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def create_redis_client(url: str, timeout: float = 2) -> redis.Redis:
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
        retry=Retry(NoBackoff(), 0),
    )
