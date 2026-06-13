"""Shared numeric formatting helpers."""

from decimal import ROUND_DOWN, Decimal


def truncate(v: float, places: int = 2) -> float:
    """Truncate a float to ``places`` decimals using ROUND_DOWN (toward zero).

    Uses Decimal(str(v)) to bypass IEEE 754 representation errors that would
    otherwise cause int(v * 100) / 100 to lose a cent on values like 0.29 or 0.58.

    ROUND_DOWN never inflates the magnitude, so this is safe for both budgets
    (a buy is never rounded up past what the cash affords) and quantities
    (a sell is never rounded into selling more than intended).
    """
    quantum = Decimal(1).scaleb(-places)  # 10**-places, e.g. 0.01 or 0.000001
    return float(Decimal(str(v)).quantize(quantum, rounding=ROUND_DOWN))


def truncate2(v: float) -> float:
    """Truncate a float to 2 decimal places (the response-currency precision)."""
    return truncate(v, 2)
