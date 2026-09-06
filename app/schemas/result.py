"""Pydantic v2 schemas for the HTTP response boundary."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_serializer

from app.core.formatting import truncate, truncate2


class AssetResultOut(BaseModel):
    id: int
    ticker: str
    current_percentage: Decimal
    desired_percentage: Decimal
    shares: Decimal
    allocated: Decimal
    ticker_price: Decimal
    fees: Decimal
    buy: Decimal
    quote_as_of: date | None = None

    @field_serializer(
        "current_percentage",
        "desired_percentage",
        "allocated",
        "fees",
    )
    def _fmt_fields(self, v: Decimal) -> float:
        return float(truncate2(v))

    @field_serializer("shares", "ticker_price")
    def _fmt_precision(self, v: Decimal) -> float:
        return float(v)

    @field_serializer("buy")
    def _fmt_buy(self, v: Decimal) -> float:
        # Whole-share mode yields integer-valued floats (5.0); fractional mode
        # yields up to 6 decimals. Monetary display fields retain two decimals.
        return float(truncate(v, 6))


class RebalanceResponse(BaseModel):
    results: list[AssetResultOut]
    total_fees: Decimal
    change: Decimal
    base_currency: str | None = None
    fx_as_of: date | None = None

    @field_serializer("total_fees", "change")
    def _fmt_totals(self, v: Decimal) -> float:
        return float(truncate2(v))
