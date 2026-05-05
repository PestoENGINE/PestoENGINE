"""Shared numeric formatting helpers."""

from decimal import ROUND_DOWN, Decimal

_CENT = Decimal("0.01")


def truncate2(v: float) -> float:
    """Truncate a float to 2 decimal places using ROUND_DOWN.

    Uses Decimal(str(v)) to bypass IEEE 754 representation errors that would
    otherwise cause int(v * 100) / 100 to lose a cent on values like 0.29 or 0.58.
    """
    return float(Decimal(str(v)).quantize(_CENT, rounding=ROUND_DOWN))
