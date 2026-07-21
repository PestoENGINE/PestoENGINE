"""Pydantic v2 schemas for the HTTP response boundary."""

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

    @field_serializer(
        "current_percentage", "desired_percentage", "shares",
        "allocated", "ticker_price", "fees",
    )
    def _fmt_fields(self, v: Decimal) -> float:
        return float(truncate2(v))

    @field_serializer("buy")
    def _fmt_buy(self, v: Decimal) -> float:
        # Whole-share mode yields integer-valued floats (5.0); fractional mode
        # yields up to 6 decimals. 6 dp is finer than any broker and keeps the
        # residual unspent cash below a cent.
        return float(truncate(v, 6))


class RebalanceResponse(BaseModel):
    results: list[AssetResultOut]
    total_fees: Decimal
    change: Decimal

    @field_serializer("total_fees", "change")
    def _fmt_totals(self, v: Decimal) -> float:
        return float(truncate2(v))
