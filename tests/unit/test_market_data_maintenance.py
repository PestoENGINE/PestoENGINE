"""Regression cases for provider identity, observation dates and transport limits."""

import gzip
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import MarketDataError
from app.core.http import MAX_RESPONSE_BYTES, provider_budget, provider_get
from app.core.log_config import SensitiveDataFilter, setup_logging
from app.fx.ecb_provider import EcbFxProvider, EcbReferenceRate
from app.market_data.alpha_vantage_provider import AlphaVantageProvider
from app.market_data.alpha_vantage_search_provider import AlphaVantageSearchProvider
from app.market_data.cache import LocalCache
from app.market_data.cached_provider import CachedMarketDataProvider
from app.market_data.provider_registry import ProviderRegistry
from app.market_data.quote import MarketQuote
from app.market_data.yahoo_finance_provider import YahooFinanceProvider
from tests.helpers import make_quote


def asset(provider=None, currency=None):
    return SimpleNamespace(ticker="SAME", provider=provider, currency=currency)


def test_same_ticker_from_different_providers_keeps_row_identity():
    yahoo = MagicMock()
    yahoo.get_quotes.return_value = {"SAME": make_quote(10)}
    alpha = MagicMock()
    alpha.get_quotes.return_value = {"SAME": make_quote(20)}
    registry = ProviderRegistry({"yahoo": yahoo, "alphavantage": alpha}, ["yahoo"])
    assert [
        q.price
        for q in registry.get_quotes_for_assets(
            [
                asset("yahoo"),
                asset("alphavantage"),
                asset(),
            ]
        )
    ] == [10, 20, 10]


def test_same_ticker_with_conflicting_currency_hints_is_fetched_separately():
    provider = MagicMock()
    provider.get_quotes.side_effect = lambda tickers, currency_hints: {
        "SAME": make_quote(10, currency=currency_hints["SAME"]),
    }
    registry = ProviderRegistry({"alphavantage": provider}, ["alphavantage"])
    quotes = registry.get_quotes_for_assets(
        [asset("alphavantage", "EUR"), asset("alphavantage", "USD")]
    )
    assert [q.currency for q in quotes] == ["EUR", "USD"]
    assert provider.get_quotes.call_count == 2


def test_incomplete_provider_response_uses_fallback():
    missing, valid = MagicMock(), MagicMock()
    missing.get_quotes.return_value = {}
    valid.get_quotes.return_value = {"SAME": make_quote(42)}
    registry = ProviderRegistry(
        {"yahoo": missing, "alphavantage": valid}, ["yahoo", "alphavantage"]
    )
    assert registry.get_quotes_for_assets([asset()])[0].price == 42


@pytest.mark.parametrize("body", [[], None, {"Global Quote": ["bad"]}, {"Global Quote": "bad"}])
def test_malformed_alpha_quote_is_a_domain_failure_without_retry(body):
    count = 0

    def respond(request):
        nonlocal count
        count += 1
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MarketDataError):
            AlphaVantageProvider("test-key", client=client).get_quotes(
                ["SAME"], currency_hints={"SAME": "USD"}
            )
    assert count == 1


@pytest.mark.parametrize("provider", ["yahoo", "alpha"])
@pytest.mark.parametrize("age", [-1, 8])
def test_stale_and_future_prices_are_rejected(provider, age):
    observation = datetime.now(UTC) - timedelta(days=age)
    body = {
        "Global Quote": {
            "05. price": "10",
            "07. latest trading day": observation.date().isoformat(),
        }
    }
    if provider == "yahoo":
        body = {
            "chart": {
                "result": [
                    {
                        "meta": {"currency": "USD"},
                        "timestamp": [observation.timestamp()],
                        "indicators": {"quote": [{"close": [10]}]},
                    }
                ]
            }
        }
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as client:
        adapter = (
            YahooFinanceProvider(client=client)
            if provider == "yahoo"
            else AlphaVantageProvider("test-key", client=client)
        )
        with pytest.raises(MarketDataError, match="observation date"):
            adapter.get_quotes(["SAME"], currency_hints={"SAME": "USD"})


def test_cached_quote_freshness_is_independent_of_cache_ttl():
    cache = LocalCache(999999)
    cache.set("market:quote:v3:yahoo:SAME:_", MarketQuote(Decimal(1), "EUR", date(2000, 1, 1)))
    provider = MagicMock()
    provider.get_quotes.return_value = {"SAME": make_quote(2)}
    assert (
        CachedMarketDataProvider(provider, cache, provider_id="yahoo")
        .get_quotes(["SAME"])["SAME"]
        .price
        == 2
    )
    provider.get_quotes.assert_called_once()


@pytest.mark.parametrize("mixed", [False, True])
def test_fx_partial_or_mixed_cache_refreshes_the_entire_required_set(mixed):
    today = date(2026, 9, 4)
    cache = LocalCache(3600)
    cache.set(
        "fx:ecb:reference:v1:USD", EcbReferenceRate("USD", Decimal(2), today - timedelta(days=1))
    )
    if mixed:
        cache.set("fx:ecb:reference:v1:CHF", EcbReferenceRate("CHF", Decimal(1), today))
    provider = EcbFxProvider(cache, today=lambda: today)
    provider._fetch_reference_rates = MagicMock(
        return_value={
            "USD": EcbReferenceRate("USD", Decimal(4), today),
            "CHF": EcbReferenceRate("CHF", Decimal(1), today),
        }
    )
    rates = provider.get_rates({"USD"}, "CHF")
    provider._fetch_reference_rates.assert_called_once_with({"USD", "CHF"})
    assert rates["USD"] == Decimal("0.25")
    assert rates.as_of == today


def test_fx_rejects_inconsistent_fetched_dates_without_caching():
    cache = MagicMock()
    cache.get.return_value = None
    provider = EcbFxProvider(cache, today=lambda: date(2026, 9, 4))
    provider._fetch_reference_rates = MagicMock(
        return_value={
            "USD": EcbReferenceRate("USD", Decimal(2), date(2026, 9, 3)),
            "CHF": EcbReferenceRate("CHF", Decimal(1), date(2026, 9, 4)),
        }
    )
    with pytest.raises(MarketDataError, match="inconsistent"):
        provider.get_rates({"USD"}, "CHF")
    cache.set.assert_not_called()


def test_http_client_reuse_supports_compressed_responses():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=gzip.compress(b'{"ok": true}'),
                headers={"Content-Encoding": "gzip"},
            )
        )
    ) as client:
        assert provider_get(client, "https://example.test", timeout=1).json() == {"ok": True}
        assert provider_get(client, "https://example.test", timeout=1).json() == {"ok": True}
        assert not client.is_closed


def test_response_size_and_total_deadline_are_enforced():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))
        )
    ) as client:
        with pytest.raises(MarketDataError, match="size limit"):
            provider_get(client, "https://example.test", timeout=1)
        with provider_budget(0), pytest.raises(MarketDataError, match="deadline"):
            provider_get(client, "https://example.test", timeout=1)


def test_successful_search_and_price_http_logs_do_not_expose_api_keys(caplog):
    secret = "test-secret-123+&"
    settings = Settings(_env_file=None, alpha_vantage_api_key=secret)
    setup_logging(settings)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=(
                    {"bestMatches": []}
                    if request.url.params["function"] == "SYMBOL_SEARCH"
                    else {
                        "Global Quote": {
                            "05. price": "10",
                            "07. latest trading day": datetime.now(UTC).date().isoformat(),
                        }
                    }
                ),
            )
        )
    ) as client:
        with caplog.at_level(logging.INFO):
            AlphaVantageSearchProvider(secret, client=client).search("IBM")
            AlphaVantageProvider(secret, client=client).get_quotes(
                ["IBM"], currency_hints={"IBM": "USD"}
            )
    assert "[REDACTED]" in caplog.text
    assert secret not in caplog.text
    assert "test-secret" not in caplog.text


def test_redaction_covers_exception_chains_and_nested_structured_fields():
    redactor = SensitiveDataFilter(
        Settings(
            _env_file=None,
            alpha_vantage_api_key="secret-xyz",
            otel_exporter_otlp_headers="Authorization=Bearer%20token-xyz",
        )
    )
    try:
        raise ValueError("secret-xyz Bearer token-xyz")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "test", logging.ERROR, __file__, 1, "failed %s", ("secret-xyz",), sys.exc_info()
        )
    record.details = {"nested": ["secret-xyz", "Bearer token-xyz"]}
    assert redactor.filter(record)
    assert "secret-xyz" not in str(record.__dict__)
    assert "token-xyz" not in str(record.__dict__)
    assert "ValueError" in record.exc_text
