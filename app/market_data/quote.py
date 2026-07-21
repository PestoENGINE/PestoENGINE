"""Typed market quote value object and currency normalization helpers."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def normalize_currency(value: str) -> str:
    """Return a canonical three-letter quote-currency code.

    ISO 4217 codes are upper-cased. Provider-specific minor-unit aliases are
    mapped explicitly instead of being silently collapsed into their major
    currency.
    """
    if not isinstance(value, str):
        raise ValueError("Currency code must be a string")
    raw = value.strip()
    # Yahoo's GBp means pence; upper-casing it to GBP would change the unit.
    code = "GBX" if raw == "GBp" else raw.upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise ValueError(f"Invalid currency code: {value!r}")
    return code


def try_normalize_currency(value: object) -> str | None:
    """Normalize optional provider metadata, returning ``None`` if unusable."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_currency(value)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Price and currency returned by a market-data provider."""

    price: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.price, Decimal):
            raise TypeError("MarketQuote price must be a Decimal")
        if not self.price.is_finite() or self.price <= 0:
            raise ValueError("MarketQuote price must be finite and positive")

        currency = normalize_currency(self.currency)
        object.__setattr__(self, "currency", currency)

    def to_cache_dict(self) -> dict[str, str]:
        return {"price": str(self.price), "currency": self.currency}

    @classmethod
    def from_cache_dict(cls, value: object) -> "MarketQuote":
        try:
            return cls(  # type: ignore[index]
                price=Decimal(value["price"]),
                currency=value["currency"],
            )
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Malformed market quote cache payload") from exc
