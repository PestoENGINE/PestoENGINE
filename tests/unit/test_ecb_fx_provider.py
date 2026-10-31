"""ECB Data Portal parsing, triangulation, cache and staleness tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import MarketDataError
from app.core.http import provider_budget
from app.fx.ecb_provider import EcbFxProvider, EcbReferenceRate
from app.market_data.cache import LocalCache

_HEADER = (
    "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,"
    "TIME_PERIOD,OBS_VALUE\n"
)


def _row(currency: str, value: str, as_of: str = "2026-07-20") -> str:
    return (
        f"EXR.D.{currency}.EUR.SP00.A,D,{currency},EUR,SP00,A,"
        f"{as_of},{value}\n"
    )


def _response(body: str, *, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.text = body
    response.status_code = status_code
    response.raise_for_status.return_value = None
    return response


def _provider(**kwargs) -> EcbFxProvider:
    return EcbFxProvider(
        LocalCache(ttl_seconds=3600),
        today=lambda: date(2026, 7, 20),
        **kwargs,
    )


@patch("app.fx.ecb_provider.httpx.get")
def test_triangulates_multiple_sources_with_one_decimal_preserving_request(mock_get):
    mock_get.return_value = _response(
        _HEADER
        + _row("CHF", "0.9000")
        + _row("GBP", "0.8000")
        + _row("USD", "1.2000")
    )

    rates = _provider().get_rates({"USD", "CHF"}, "GBP")

    # Add the target series to the same batch.
    assert set(rates) == {"USD", "CHF"}
    assert rates["USD"] == Decimal("0.8") / Decimal("1.2")
    assert rates["CHF"] == Decimal("0.8") / Decimal("0.9")
    assert mock_get.call_count == 1
    assert "D.CHF+GBP+USD.EUR.SP00.A" in mock_get.call_args.args[0]


@patch("app.fx.ecb_provider.httpx.get")
def test_direct_eur_conversions_are_inverted_correctly(mock_get):
    mock_get.return_value = _response(_HEADER + _row("USD", "1.25"))
    usd_to_eur = _provider().get_rates({"USD"}, "EUR")["USD"]
    assert usd_to_eur == Decimal("0.8")

    mock_get.reset_mock()
    mock_get.return_value = _response(_HEADER + _row("USD", "1.25"))
    eur_to_usd = _provider().get_rates({"EUR"}, "USD")["EUR"]
    assert eur_to_usd == Decimal("1.25")


@patch("app.fx.ecb_provider.httpx.get")
def test_gbx_minor_unit_is_normalized_before_ecb_conversion(mock_get):
    mock_get.return_value = _response(_HEADER + _row("GBP", "0.8000"))

    gbx_to_eur = _provider().get_rates({"GBX"}, "EUR")["GBX"]

    assert gbx_to_eur == Decimal("0.0125")


@patch("app.fx.ecb_provider.httpx.get")
def test_gbx_to_gbp_is_fixed_and_needs_no_network_call(mock_get):
    rate = _provider().get_rates({"GBX"}, "GBP")["GBX"]

    assert rate == Decimal("0.01")
    mock_get.assert_not_called()


@patch("app.fx.ecb_provider.httpx.get")
def test_fresh_cache_hit_avoids_second_network_call(mock_get):
    mock_get.return_value = _response(_HEADER + _row("USD", "1.142600"))
    provider = _provider()

    first = provider.get_rates({"USD"}, "EUR")["USD"]
    second = provider.get_rates({"USD"}, "EUR")["USD"]

    assert first == second == Decimal("1") / Decimal("1.142600")
    assert mock_get.call_count == 1


def test_cached_currency_does_not_wait_for_an_unrelated_refresh():
    today = date(2026, 7, 20)
    cache = LocalCache(ttl_seconds=3600)
    cache.set("fx:ecb:reference:v1:USD", EcbReferenceRate("USD", Decimal("1.25"), today))
    provider = EcbFxProvider(cache, today=lambda: today)
    started, release = Event(), Event()

    def fetch(currencies):
        started.set()
        assert release.wait(5)
        return {c: EcbReferenceRate(c, Decimal(160), today) for c in currencies}

    provider._fetch_reference_rates = fetch
    with ThreadPoolExecutor(max_workers=1) as executor:
        refresh = executor.submit(provider.get_rates, {"JPY"}, "EUR")
        try:
            assert started.wait(2)
            with provider_budget(0.2):
                rates = provider.get_rates({"USD"}, "EUR")
            assert rates["USD"] == Decimal("0.8")
            assert rates.as_of == today
        finally:
            release.set()
        refresh.result(timeout=2)


@patch("app.fx.ecb_provider.httpx.get")
def test_missing_ecb_series_fails_without_retry(mock_get):
    mock_get.return_value = _response("", status_code=404)

    with pytest.raises(MarketDataError, match="KWD"):
        _provider().get_rates({"KWD"}, "EUR")
    assert mock_get.call_count == 1


@patch("app.fx.ecb_provider.httpx.get")
def test_stale_or_future_observations_fail_closed(mock_get):
    mock_get.return_value = _response(
        _HEADER + _row("USD", "1.2", as_of="2026-07-10")
    )
    with pytest.raises(MarketDataError, match="stale"):
        _provider(max_age_days=7).get_rates({"USD"}, "EUR")

    mock_get.return_value = _response(
        _HEADER + _row("USD", "1.2", as_of="2026-07-21")
    )
    with pytest.raises(MarketDataError, match="future"):
        _provider(max_age_days=7).get_rates({"USD"}, "EUR")


@patch("app.core.http.time.sleep")
@patch("app.fx.ecb_provider.httpx.get")
def test_malformed_csv_fails_without_retry_market_data_error(mock_get, mock_sleep):
    mock_get.return_value = _response("not,the,expected,header\n")

    with pytest.raises(MarketDataError, match="after 1 attempts"):
        _provider().get_rates({"USD"}, "EUR")

    assert mock_get.call_count == 1
    assert mock_sleep.call_count == 0
