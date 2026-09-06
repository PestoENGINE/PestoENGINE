"""Typed market quote value object and currency normalization helpers."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from app.core.exceptions import MarketDataError


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
    as_of: date | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.price, Decimal):
            raise TypeError("MarketQuote price must be a Decimal")
        if not self.price.is_finite() or not Decimal("1e-18") <= self.price <= Decimal("1e12"):
            raise ValueError("MarketQuote price must be finite and between 1e-18 and 1e12")

        if self.as_of is not None and type(self.as_of) is not date:
            raise ValueError("Quote observation date must be a date")
        currency = normalize_currency(self.currency)
        object.__setattr__(self, "currency", currency)

    def assert_fresh(self, max_age_days: int = 7, *, today: date | None = None) -> None:
        today = today or datetime.now(UTC).date()
        if self.as_of is None or not 0 <= (today - self.as_of).days <= max_age_days:
            raise MarketDataError("Quote observation date is missing, stale or in the future")

    def to_cache_dict(self) -> dict[str, str | None]:
        return {
            "price": str(self.price),
            "currency": self.currency,
            "as_of": self.as_of.isoformat() if self.as_of else None,
        }

    @classmethod
    def from_cache_dict(cls, value: object) -> "MarketQuote":
        try:
            if not isinstance(value, dict):
                raise ValueError("Expected an object")
            return cls(
                price=Decimal(value["price"]),
                currency=value["currency"],
                as_of=date.fromisoformat(value["as_of"]) if value.get("as_of") else None,
            )
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Malformed market quote cache payload") from exc
