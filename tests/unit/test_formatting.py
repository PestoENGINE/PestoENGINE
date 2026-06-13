"""Unit tests for the numeric formatting helpers."""

from app.core.formatting import truncate, truncate2


def test_truncate2_truncates_toward_zero():
    """truncate2 keeps the existing 2-decimal ROUND_DOWN contract."""
    assert truncate2(1.239) == 1.23
    assert truncate2(0.29) == 0.29  # the FP-representation edge case it was built for


def test_truncate_defaults_to_two_places():
    """truncate() with no places argument behaves like truncate2()."""
    assert truncate(1.239) == 1.23


def test_truncate_to_six_places_rounds_down():
    """Fractional-share precision: 6 decimals, never rounding up (no overspend)."""
    assert truncate(3.3333339, 6) == 3.333333


def test_truncate_negative_truncates_toward_zero():
    """Sells (negative quantities) truncate toward zero, never over-selling."""
    assert truncate(-4.7567891, 6) == -4.756789
