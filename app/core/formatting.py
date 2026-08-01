"""Shared numeric formatting helpers."""

from decimal import ROUND_DOWN, Decimal

DecimalInput = Decimal | int | float | str


def as_decimal(v: DecimalInput) -> Decimal:
    """Convert a boundary number to Decimal without inheriting float noise."""
    return v if isinstance(v, Decimal) else Decimal(str(v))


def truncate(v: DecimalInput, places: int = 2) -> Decimal:
    """Truncate to ``places`` decimals using ROUND_DOWN."""
    quantum = Decimal(1).scaleb(-places)  # 10**-places, e.g. 0.01 or 0.000001
    return as_decimal(v).quantize(quantum, rounding=ROUND_DOWN)


def truncate2(v: DecimalInput) -> Decimal:
    """Truncate a number to two response-currency decimal places."""
    return truncate(v, 2)
