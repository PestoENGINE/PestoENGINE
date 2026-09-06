"""Unit tests for LocalCache and CachedMarketDataProvider."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.metrics import MeterProvider

from app.fx.ecb_provider import EcbReferenceRate
from app.market_data.base import AbstractMarketDataProvider
from app.market_data.cache import LocalCache
from app.market_data.cached_provider import _KEY_PREFIX, CachedMarketDataProvider
from app.market_data.quote import MarketQuote
from app.market_data.redis_cache import RedisCache
from tests.helpers import make_quote, make_quotes

_NOOP_MP = MeterProvider()
_TEST_KEY_PREFIX = _KEY_PREFIX + "test:"


def _make_cache(ttl: int = 300) -> tuple[LocalCache, MagicMock]:
    clock = MagicMock(return_value=0.0)
    return LocalCache(ttl_seconds=ttl, clock=clock), clock


def _key(ticker: str, currency: str | None = None) -> str:
    return _TEST_KEY_PREFIX + ticker + ":" + (currency or "_")


def _make_provider(prices: dict):
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_quotes.return_value = make_quotes(prices)
    cache = LocalCache(ttl_seconds=300)
    provider = CachedMarketDataProvider(
        mock, cache, provider_id="test", meter_provider=_NOOP_MP,
    )
    return provider, mock, cache


def test_get_returns_none_for_missing_key():
    cache, _ = _make_cache()
    assert cache.get("x") is None


def test_set_and_get_returns_value():
    cache, _ = _make_cache()
    quote = make_quote("42.001")
    cache.set("k", quote)
    assert cache.get("k") == quote


def test_get_returns_none_after_ttl_expires():
    cache, clock = _make_cache(ttl=60)
    cache.set("k", make_quote(99))
    clock.return_value = 61
    assert cache.get("k") is None


def test_get_returns_value_before_ttl_expires():
    cache, clock = _make_cache(ttl=60)
    quote = make_quote(99)
    cache.set("k", quote)
    clock.return_value = 59
    assert cache.get("k") == quote


def test_expired_key_is_removed_from_store():
    cache, clock = _make_cache(ttl=10)
    cache.set("k", make_quote(1))
    clock.return_value = 11
    cache.get("k")
    with cache._lock:
        assert "k" not in cache._store


def test_overwrite_resets_ttl():
    cache, clock = _make_cache(ttl=60)
    cache.set("k", make_quote(1))
    clock.return_value = 50
    latest = make_quote(2)
    cache.set("k", latest)
    clock.return_value = 100
    assert cache.get("k") == latest


def test_all_miss_calls_underlying_provider():
    provider, mock, _ = _make_provider({"A": 10, "B": 20})
    assert provider.get_quotes(["A", "B"]) == make_quotes({"A": 10, "B": 20})
    mock.get_quotes.assert_called_once_with(["A", "B"], currency_hints={})


def test_all_hit_does_not_call_underlying_provider():
    provider, mock, cache = _make_provider({})
    expected = {"A": make_quote(10), "B": make_quote(20)}
    for ticker, quote in expected.items():
        cache.set(_key(ticker), quote)
    assert provider.get_quotes(["A", "B"]) == expected
    mock.get_quotes.assert_not_called()


def test_partial_hit_calls_provider_only_for_misses():
    provider, mock, cache = _make_provider({"B": 20})
    cache.set(_key("A"), make_quote(10))
    result = provider.get_quotes(["A", "B"])
    assert {ticker: quote.price for ticker, quote in result.items()} == {"A": 10, "B": 20}
    mock.get_quotes.assert_called_once_with(["B"], currency_hints={})


def test_fetched_quotes_are_written_to_cache():
    provider, _, cache = _make_provider({"A": "55.009"})
    provider.get_quotes(["A"])
    assert cache.get(_key("A")) == make_quote("55.009")


def test_currency_hint_partitions_cache_keys():
    provider, mock, cache = _make_provider({"A": 55})
    provider.get_quotes(["A"], currency_hints={"A": "EUR"})
    assert cache.get(_key("A", "EUR")) == make_quote(55)
    assert cache.get(_key("A")) is None
    mock.get_quotes.assert_called_once_with(["A"], currency_hints={"A": "EUR"})


def test_provider_error_propagates():
    mock = MagicMock(spec=AbstractMarketDataProvider)
    mock.get_quotes.side_effect = RuntimeError("feed down")
    provider = CachedMarketDataProvider(mock, LocalCache(300), provider_id="test")
    with pytest.raises(RuntimeError, match="feed down"):
        provider.get_quotes(["A"])


def test_providers_use_separate_cache_namespaces():
    cache = LocalCache(ttl_seconds=300)
    yahoo_mock = MagicMock(spec=AbstractMarketDataProvider)
    yahoo_mock.get_quotes.return_value = make_quotes({"VOO": 500})
    alpha_mock = MagicMock(spec=AbstractMarketDataProvider)
    alpha_mock.get_quotes.return_value = make_quotes({"VOO": 499})
    yahoo = CachedMarketDataProvider(
        yahoo_mock, cache, provider_id="yahoo", meter_provider=_NOOP_MP,
    )
    alpha = CachedMarketDataProvider(
        alpha_mock, cache, provider_id="alphavantage", meter_provider=_NOOP_MP,
    )
    yahoo.get_quotes(["VOO"])
    alpha.get_quotes(["VOO"])
    yahoo_mock.get_quotes.assert_called_once()
    alpha_mock.get_quotes.assert_called_once()


@pytest.mark.parametrize(
    ("value", "encode", "decode"),
    [
        (make_quote("123.456"), MarketQuote.to_cache_dict, MarketQuote.from_cache_dict),
        (EcbReferenceRate("USD", Decimal("1.1426"), date(2026, 7, 20)),
         EcbReferenceRate.to_cache_dict, EcbReferenceRate.from_cache_dict),
    ],
)
def test_redis_cache_round_trips_typed_values(value, encode, decode):
    cache = RedisCache.__new__(RedisCache)
    cache._client = MagicMock()
    cache._ttl = 300
    cache._encode = encode
    cache._decode = decode
    cache.set("key", value)
    key, ttl, raw = cache._client.setex.call_args.args
    assert (key, ttl, json.loads(raw)) == ("key", 300, encode(value))
    cache._client.get.return_value = raw
    assert cache.get("key") == value
    cache._client.get.return_value = "not-json"
    assert cache.get("key") is None
