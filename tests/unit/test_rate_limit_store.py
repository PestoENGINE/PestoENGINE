"""Unit tests for LocalRateLimitStore and RedisRateLimitStore."""

import threading
from unittest.mock import MagicMock

from app.rate_limit.local_store import LocalRateLimitStore


def _make_store(now: float = 0.0):
    clock = MagicMock(return_value=now)
    store = LocalRateLimitStore(clock=clock)
    return store, clock


def test_first_call_returns_one():
    store, _ = _make_store()
    assert store.increment("key", 60) == 1


def test_second_call_increments():
    store, _ = _make_store()
    store.increment("key", 60)
    assert store.increment("key", 60) == 2


def test_third_call_increments():
    store, _ = _make_store()
    store.increment("key", 60)
    store.increment("key", 60)
    assert store.increment("key", 60) == 3


def test_different_keys_are_independent():
    store, _ = _make_store()
    store.increment("a", 60)
    store.increment("a", 60)
    assert store.increment("b", 60) == 1


def test_expired_window_resets_to_one():
    store, clock = _make_store(now=0.0)
    store.increment("key", 60)
    store.increment("key", 60)
    clock.return_value = 61.0
    assert store.increment("key", 60) == 1


def test_window_expires_at_exact_boundary():
    store, clock = _make_store(now=0.0)
    store.increment("key", 60)
    store.increment("key", 60)
    clock.return_value = 60.0  # exactly at expiry boundary
    assert store.increment("key", 60) == 1


def test_unexpired_window_continues():
    store, clock = _make_store(now=0.0)
    store.increment("key", 60)
    store.increment("key", 60)
    clock.return_value = 59.9
    assert store.increment("key", 60) == 3


def test_thread_safety():
    store, _ = _make_store(now=0.0)
    results = []
    results_lock = threading.Lock()

    def worker():
        count = store.increment("shared_key", 60)
        with results_lock:
            results.append(count)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 50
    assert sorted(results) == list(range(1, 51))


# RedisRateLimitStore

from app.rate_limit.redis_store import RedisRateLimitStore


def _make_redis_store(incr_return: int = 1):
    client = MagicMock()
    client.incr.return_value = incr_return
    store = RedisRateLimitStore(client)
    return store, client


def test_redis_incr_called_on_every_increment():
    store, client = _make_redis_store(incr_return=1)
    store.increment("key", 60)
    client.incr.assert_called_once_with("key")


def test_redis_expire_set_on_first_insert():
    store, client = _make_redis_store(incr_return=1)
    store.increment("key", 60)
    client.expire.assert_called_once_with("key", 60)


def test_redis_expire_not_set_on_subsequent_calls():
    store, client = _make_redis_store(incr_return=2)
    store.increment("key", 60)
    client.expire.assert_not_called()


def test_redis_returns_incr_value():
    store, client = _make_redis_store(incr_return=5)
    result = store.increment("key", 60)
    assert result == 5
