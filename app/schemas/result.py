"""Pydantic v2 schemas for the HTTP response boundary."""

from pydantic import BaseModel, field_serializer

from app.core.formatting import truncate, truncate2


class AssetResultOut(BaseModel):
    id: int
    ticker: str
    current_percentage: float
    desired_percentage: float
    shares: float
    allocated: float
    ticker_price: float
    fees: float
    buy: float

    @field_serializer(
        "current_percentage", "desired_percentage", "shares",
        "allocated", "ticker_price", "fees",
    )
    def _fmt_fields(self, v: float) -> float:
        return truncate2(v)

    @field_serializer("buy")
    def _fmt_buy(self, v: float) -> float:
        # Whole-share mode yields integer-valued floats (5.0); fractional mode
        # yields up to 6 decimals. 6 dp is finer than any broker and keeps the
        # residual unspent cash below a cent.
        return truncate(v, 6)


class RebalanceResponse(BaseModel):
    results: list[AssetResultOut]
    total_fees: float
    change: float

    @field_serializer("total_fees", "change")
    def _fmt_totals(self, v: float) -> float:
        return truncate2(v)
