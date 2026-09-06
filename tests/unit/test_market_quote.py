"""Essential quote value and cache-boundary tests."""

from decimal import Decimal

import pytest

from app.market_data.quote import MarketQuote, normalize_currency


def test_quote_normalizes_currency_and_preserves_decimal_price():
    quote = MarketQuote(price=Decimal("0.004900"), currency="usd")

    assert quote.currency == "USD"
    assert quote.price == Decimal("0.004900")
    assert MarketQuote.from_cache_dict(quote.to_cache_dict()) == quote


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity"])
def test_quote_rejects_invalid_prices(price):
    with pytest.raises(ValueError, match="finite and between"):
        MarketQuote(price=Decimal(price), currency="EUR")


def test_quote_requires_decimal_and_valid_cache_payload():
    with pytest.raises(TypeError, match="Decimal"):
        MarketQuote(price=1.25, currency="EUR")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        MarketQuote.from_cache_dict({"price": "1"})


def test_yahoo_pence_code_is_not_mistaken_for_pounds():
    assert normalize_currency("GBp") == "GBX"
    assert normalize_currency("gbp") == "GBP"
