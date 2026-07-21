"""Small factories shared by currency-aware market-data and FX tests."""

from decimal import Decimal

from app.market_data.quote import MarketQuote


def make_quote(
    price: Decimal | int | float | str,
    *,
    currency: str = "EUR",
) -> MarketQuote:
    return MarketQuote(price=Decimal(str(price)), currency=currency)


def make_quotes(
    prices: dict[str, Decimal | int | float | str],
    *,
    currency: str = "EUR",
) -> dict[str, MarketQuote]:
    return {
        ticker: make_quote(price, currency=currency)
        for ticker, price in prices.items()
    }
