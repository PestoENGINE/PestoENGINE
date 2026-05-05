"""Unit tests for LocalCache and CachedMarketDataProvider."""

from unittest.mock import MagicMock

from app.market_data.cache import LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider, _KEY_PREFIX
from app.market_data.base import AbstractMarketDataProvider


# ---------------------------------------------------------------------------
# LocalCache
# ---------------------------------------------------------------------------

def _make_cache(ttl: int = 300) -> tuple[LocalCache, MagicMock]:
    clock = MagicMock(return_value=0.0)
    cache = LocalCache(ttl_seconds=ttl, clock=clock)
    return cache, clock


def test_get_returns_none_for_missing_key():
    cache, _ = _make_cache()
    assert cache.get("x") is None


def test_set_and_get_returns_value():
    cache, _ = _make_cache()
    cache.set("k", 42.0)
    assert cache.get("k") == 42.0


def test_get_returns_none_after_ttl_expires():
    cache, clock = _make_cache(ttl=60)
    clock.return_value = 0.0
    cache.set("k", 99.0)
    clock.return_value = 61.0
    assert cache.get("k") is None


def test_get_returns_value_before_ttl_expires():
    cache, clock = _make_cache(ttl=60)
    clock.return_value = 0.0
    cache.set("k", 99.0)
    clock.return_value = 59.0
    assert cache.get("k") == 99.0


def test_expired_key_is_removed_from_store():
    cache, clock = _make_cache(ttl=10)
    clock.return_value = 0.0
    cache.set("k", 1.0)
    clock.return_value = 11.0
    cache.get("k")
    with cache._lock:
        assert "k" not in cache._store


def test_overwrite_resets_ttl():
    cache, clock = _make_cache(ttl=60)
    clock.return_value = 0.0
    cache.set("k", 1.0)
    clock.return_value = 50.0
    cache.set("k", 2.0)
    clock.return_value = 100.0
    assert cache.get("k") == 2.0


# ---------------------------------------------------------------------------
# CachedMarketDataProvider
# ---------------------------------------------------------------------------

def _make_provider(prices: dict) -> tuple[CachedMarketDataProvider, MagicMock, LocalCache]:
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.return_value = prices
    cache = LocalCache(ttl_seconds=300)
    provider = CachedMarketDataProvider(mock, cache)
    return provider, mock, cache


def test_all_miss_calls_underlying_provider():
    provider, mock, _ = _make_provider({"A": 10.0, "B": 20.0})
    result = provider.get_prices(["A", "B"])
    mock.get_prices.assert_called_once_with(["A", "B"])
    assert result == {"A": 10.0, "B": 20.0}


def test_all_hit_does_not_call_underlying_provider():
    provider, mock, cache = _make_provider({})
    cache.set(_KEY_PREFIX + "A", 10.0)
    cache.set(_KEY_PREFIX + "B", 20.0)
    result = provider.get_prices(["A", "B"])
    mock.get_prices.assert_not_called()
    assert result == {"A": 10.0, "B": 20.0}


def test_partial_hit_calls_provider_only_for_misses():
    provider, mock, cache = _make_provider({"B": 20.0})
    cache.set(_KEY_PREFIX + "A", 10.0)
    result = provider.get_prices(["A", "B"])
    mock.get_prices.assert_called_once_with(["B"])
    assert result == {"A": 10.0, "B": 20.0}


def test_fetched_prices_are_written_to_cache():
    provider, _, cache = _make_provider({"A": 55.0})
    provider.get_prices(["A"])
    assert cache.get(_KEY_PREFIX + "A") == 55.0


def test_provider_error_propagates():
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_prices.side_effect = RuntimeError("feed down")
    cache = LocalCache(ttl_seconds=300)
    p = CachedMarketDataProvider(mock, cache)
    try:
        p.get_prices(["A"])
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "feed down" in str(exc)
