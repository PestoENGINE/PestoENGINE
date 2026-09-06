"""Unit tests for LocalRateLimitStore and RedisRateLimitStore."""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import fakeredis

from app.rate_limit.local_store import LocalRateLimitStore
from app.rate_limit.redis_store import RedisRateLimitStore


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


def test_redis_atomic_increment_and_ttl():
    client = fakeredis.FakeRedis()
    store = RedisRateLimitStore(client)
    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(pool.map(lambda _: store.increment("key", 60), range(50)))
    assert sorted(counts) == list(range(1, 51))
    assert 0 < client.ttl("key") <= 60
    client.expire("key", 20)
    assert store.increment("key", 60) == 51
    assert 0 < client.ttl("key") <= 20


def test_redis_repairs_a_counter_without_expiry():
    client = fakeredis.FakeRedis()
    client.set("key", 7)
    assert RedisRateLimitStore(client).increment("key", 60) == 8
    assert 0 < client.ttl("key") <= 60
