"""Pydantic v2 schemas for the HTTP request boundary."""

from pydantic import BaseModel, Field, model_validator


class AssetIn(BaseModel):
    ticker: str = Field(min_length=1)
    desired_percentage: float = Field(ge=0, le=100)
    shares: float = Field(ge=0)
    fees: float = Field(ge=0)
    percentage_fee: bool = False

    @model_validator(mode="after")
    def check_percentage_fee_cap(self) -> "AssetIn":
        if self.percentage_fee and self.fees > 100:
            raise ValueError(
                f"Asset '{self.ticker}': percentage fee cannot exceed 100, got {self.fees}."
            )
        return self


class RebalanceRequest(BaseModel):
    only_buy: bool
    increment: float = Field(ge=0)
    optimal_redistribute: bool = False
    assets: list[AssetIn] = Field(min_length=1)

    @model_validator(mode="after")
    def check_percentages_sum(self) -> "RebalanceRequest":
        total = sum(a.desired_percentage for a in self.assets)
        if round(total, 2) != 100.0:
            raise ValueError(
                f"desired_percentage must sum to 100.00, got {total:.2f}"
            )
        return self
